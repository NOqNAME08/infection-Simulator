import math
import random

import pandas as pd

import Location
import Person


class Simulation:

  # 사람을 이 크기의 소그룹으로 나눠 각 그룹을 하나의 접촉 공간으로 취급한다.
  # 카페는 방문할 때마다 방문자를 다시 섞어 2명씩 임시 그룹에 배정한다.
  GROUP_SIZES = {
      "school": 20,
      "company": 15,
      "cafe": 2,
      "academy": 10,
      "home": 4,
  }

  def __init__(self):
    # 시뮬레이션 결과와 사람별 접촉 그래프(인접 리스트)를 저장한다.
    self.result: pd.DataFrame = pd.DataFrame(columns=["day", "infected"])
    self.people: dict[int, Person.Person] = {}
    self.graph: dict[int, list[int]] = {}
    # locations는 장소 유형별 그룹 목록, person_locations는 개인별 소속 그룹이다.
    self.locations: dict[str, list[Location.Location]] = {}
    self.person_locations: dict[int, dict[str, Location.Location]] = {}

    # 시간은 누적 시간(시간 단위)과 하루 안의 시각(0~23)을 함께 추적한다.
    self.day: int = 0
    self.hour: int = 0
    self.total_hours: int = 0
    self.is_distancing_active: bool = False
    # 전파/접촉 확률과 면역 효과는 0~1 비율로 설정한다.
    self.infection_probability: float = 0.15  # 간선이 있을 때 최대 전파 확률
    self.contact_probability: float = 0.15  # 비가정 사람 쌍별 하루 간선 생성 확률
    self.household_transmission_probability: float = 0.28  # 가구원 한 명에게 전파될 누적 기준 확률
    self.vaccine_effectiveness: float = 0.70  # 백신으로 줄어드는 감염 확률 비율
    self.recovered_probability: float = 0.85  # 회복으로 줄어드는 재감염 확률 비율
    self.recovery_hours: int = 7 * 24  # 평균 회복 기간(7일)
    self.recovery_variation_hours: int = 24  # 개인별 회복 시점 편차(±1일)
    self.isolation_probability: float = 0.40  # 감염자의 격리 일정 생성 확률
    # 하루 중 이미 접촉 확률을 추첨한 사람 쌍. 시간대가 달라도 재추첨하지 않는다.
    self._daily_pairs: set[tuple[int, int]] = set()


  @staticmethod
  def infectivity_curve(age_hours: int) -> float:
    """감염 후 경과 시간에 따른 상대 감염력(3.5일 정점의 이차식 가정)."""
    if age_hours < 0 or age_hours >= 7 * 24:
      return 0.0
    # 꼭짓점이 84시간(3.5일)인 아래로 열린 포물선. 범위 밖 값은 0으로 제한한다.
    return max(0.0, 1.0 - ((age_hours - 84) / 84) ** 2)


  def _household_daily_probability(
      self,
      infected: Person.Person,
      age_day: int,
  ) -> float:
    """개인의 감염 기간을 기준으로 일별 가정 내 전파 확률을 계산한다."""
    if infected.infected_at_hour is None or infected.recovery_at_hour is None:
      return 0.0

    # 감염력 곡선은 7일까지 정의되므로 그 안에서 회복 전까지의 날짜만 사용한다.
    duration = min(
        infected.recovery_at_hour - infected.infected_at_hour,
        self.recovery_hours,
    )
    day_count = math.ceil(duration / 24)
    if age_day < 0 or age_day >= day_count:
      return 0.0

    weights = [
        self.infectivity_curve(min(day * 24 + 12, duration - 1))
        for day in range(day_count)
    ]
    weight_sum = sum(weights)
    if weight_sum == 0:
      return 0.0

    # 회복 전 일별 위험을 누적하면 가정 내 기준 전파 확률이 된다.
    return 1.0 - (
        1.0 - self.household_transmission_probability
    ) ** (weights[age_day] / weight_sum)


  @staticmethod
  def _make_groups(name: str, people_count: int, group_size: int):
    # 인구 규모를 수용할 수 있는 만큼 그룹을 만들고 마지막 그룹은 일부만 채운다.
    group_count = max(1, math.ceil(people_count / group_size))

    return [
        Location.Location(f"{name}_{index}", group_size)
        for index in range(group_count)
    ]


  def infected_count(self) -> int:
    # 현재 감염 상태인 사람만 센다. 회복자는 포함하지 않는다.
    return sum(person.state == "Infected" for person in self.people.values())


  def create_schedule(self, person: Person.Person) -> dict[int, Location.Location]:
    # 하루 일정을 만들 때 감염자의 격리 여부를 결정한다.
    home = self.person_locations[person.ID]["home"]
    person_locations = self.person_locations[person.ID]

    if person.state == "Infected":

      if not person.is_isolated and random.random() < self.isolation_probability:
        person.is_isolated = True

      if person.is_isolated:
        # 격리된 감염자는 회복할 때까지 다음 일정을 전부 집으로 설정한다.
        return {hour: home for hour in range(24)}

    # 기본 일정은 집이며, 낮에는 소속 학교/회사, 저녁에는 학원/카페를 배정한다.
    schedule = {hour: home for hour in range(24)}

    works_from_home_today = (
        self.is_distancing_active and random.random() < 0.5
    )

    for hour in range(9, 17):

      if works_from_home_today:
        schedule[hour] = home
      else:
        schedule[hour] = person_locations[person.occupation]

    # 학생 중 일부는 저녁에 학원에 가며, 학원 일정이 없는 경우 카페 방문을 추첨한다.
    attends_academy = (
        person.occupation == "school" and random.random() < 0.4
    )

    for hour in range(17, 21):

      if attends_academy and hour < 20:
        schedule[hour] = person_locations["academy"]

      elif not self.is_distancing_active and random.random() < 0.3:
        schedule[hour] = person_locations["cafe"]

    return schedule


  def setup(self, size: int = 100, random_seed: int = 0) -> bool:
    # 같은 시드와 같은 입력으로 재현 가능한 난수 흐름을 만든다.
    if size <= 0:
      raise ValueError("size must be greater than 0")
    #초기화
    random.seed(random_seed)
    self.people.clear()
    self.graph.clear()
    self.person_locations.clear()
    self.day = self.hour = self.total_hours = 0
    self.is_distancing_active = False
    self.result = pd.DataFrame(columns=["day", "infected"])
    self._daily_pairs.clear()

    # 각 장소 유형을 정해진 그룹 크기로 나눠 필요한 그룹 객체를 만든다.
    self.locations = {
        name: self._make_groups(name, size, group_size)
        for name, group_size in self.GROUP_SIZES.items()
    }

    home_groups = self.locations["home"]
    school_groups = self.locations["school"]
    company_groups = self.locations["company"]
    academy_groups = self.locations["academy"]

    # 실험 인원은 학생 또는 회사원으로 무작위 배정한다.
    occupations = [random.choice(["school", "company"]) for _ in range(size)]

    school_ids = [
        person_id
        for person_id, occupation in enumerate(occupations)
        if occupation == "school"
    ]

    company_ids = [
        person_id
        for person_id, occupation in enumerate(occupations)
        if occupation == "company"
    ]

    random.shuffle(school_ids)
    random.shuffle(company_ids)
    home_ids = list(range(size))
    random.shuffle(home_ids)

    # 같은 직업 안에서는 섞어서 소그룹에 배정하고, 가구도 무작위로 구성한다.
    assignment: dict[int, dict[str, Location.Location]] = {}
    for group_ids, groups, category in (
        (school_ids, school_groups, "school"),
        (company_ids, company_groups, "company"),
        (home_ids, home_groups, "home"),
    ):
      # 그룹 번호는 배정 순번을 그룹 크기로 나눈 몫으로 계산한다.
      # 예: 20명 그룹이면 순번 0~19는 0번 그룹, 20~39는 1번 그룹이다.
      for position, person_id in enumerate(group_ids):
        group_index = position // self.GROUP_SIZES[category]
        assignment.setdefault(person_id, {})[category] = groups[group_index]

    # 학교 그룹에 속한 학생은 학원 그룹도 하나 배정받는다.
    # 학생들을 10명 단위로 학원 그룹에 나눈다.
    for position, person_id in enumerate(school_ids):
      academy_index = position // self.GROUP_SIZES["academy"]
      assignment[person_id]["academy"] = academy_groups[academy_index]
      assignment[person_id]["cafe"] = self.locations["cafe"][0]

    for person_id in company_ids:
      assignment[person_id]["cafe"] = self.locations["cafe"][0]

    # 사람 객체를 만들고 0시의 위치를 집으로 설정한다.
    for person_id, occupation in enumerate(occupations):
      person = Person.Person(person_id, {}, occupation)
      # 이 사람의 집·직장/학교·학원·카페 그룹을 조회할 수 있게 저장한다.
      self.person_locations[person_id] = assignment[person_id]
      person.schedule = self.create_schedule(person)
      # 시뮬레이션 시작 시각은 0시이므로 최초 위치는 집이다.
      person.cur_location = assignment[person_id]["home"]
      person.cur_location.people.append(person_id)
      self.people[person_id] = person
      # 기존 가정에 따라 인구의 40%를 백신 접종자로 둔다.
      if random.random() < 0.4:
        person.vaccine = True
      # 아직 접촉 간선이 없는 빈 인접 리스트를 만든다.
      self.graph[person_id] = []

    # 초기 감염자는 감염 사실을 아직 모르는 상태로 보고 일반 일정을 유지한다.
    # 이후 다음 날 일정을 만들 때 다른 감염자처럼 격리 여부를 추첨한다.
    initial_infected_count = max(1, size // 20)

    for person in random.sample(list(self.people.values()), initial_infected_count):
      self._mark_infected(person, self.total_hours)

    return True


  def _mark_infected(self, person: Person.Person, infection_hour: int) -> None:
    """감염 상태와 개인별 회복 예정 시각을 함께 설정한다."""
    duration = self.recovery_hours + random.randint(
        -self.recovery_variation_hours,
        self.recovery_variation_hours,
    )
    person.state = "Infected"
    person.infected_at = person.cur_location
    person.infected_at_hour = infection_hour
    person.recovery_at_hour = infection_hour + duration
    person.is_isolated = False


  def recovered_check(self) -> None:
    # 개인별 회복 예정 시각이 되면 회복 상태로 바꾸고 격리 플래그를 해제한다.
    for person in self.people.values():

      if (
          person.state == "Infected"
          and person.recovery_at_hour is not None
          and self.total_hours >= person.recovery_at_hour
      ):

        person.infected_at_hour = None
        person.recovery_at_hour = None
        person.state = "Recovered"
        person.infected_at = None
        person.is_isolated = False
        person.schedule = self.create_schedule(person)


  def contact_check(self) -> None:
    # 현재 같은 장소에 있는 쌍을 살핀다. 집은 별도의 가정 전파 계산에서 처리한다.
    current_locations = {
        person.cur_location
        for person in self.people.values()
        if person.cur_location is not None
    }
    # 장소 이름순으로 고정해 난수 추첨 순서도 실행마다 같게 한다.
    for location in sorted(current_locations, key=lambda item: item.name):
      if location.name.startswith("home_"):
        continue
      here = location.people

      for index, person_a in enumerate(here):

        for person_b in here[index + 1:]:
          pair = (min(person_a, person_b), max(person_a, person_b))
          # 같은 쌍은 하루에 한 번만 추첨하므로 여러 시간 함께 있어도 15%가 누적되지 않는다.

          if pair in self._daily_pairs: # 위 주석과 같이 중복 제거 의미
            continue

          self._daily_pairs.add(pair) # 페어의 접촉을 확인 하지 않았으면 확률 따지기.

          if random.random() < self.contact_probability:
            self.graph[pair[0]].append(pair[1])
            self.graph[pair[1]].append(pair[0])


  def _effective_probability(
      self,
      person: Person.Person,
      neighbor: Person.Person,
  ) -> float:
    # 비가정 접촉의 전파 확률 = 최대 전파율 × 감염력 곡선 × 면역 효과 보정.
    infection_hour = person.infected_at_hour

    infection_hour = (
        infection_hour if infection_hour is not None else self.total_hours
    )

    age = self.total_hours - infection_hour
    probability = self.infection_probability * self.infectivity_curve(age)

    if neighbor.vaccine:
      probability *= 1 - self.vaccine_effectiveness

    if neighbor.state == "Recovered":
      probability *= 1 - self.recovered_probability

    return probability


  def infection_phase(self) -> bool:
    # 하루 동안 기록한 접촉 간선에 대해 감염 여부를 판정한다.
    newly_infected: set[int] = set()

    for person_id, neighbors in self.graph.items():
      person = self.people[person_id]

      if person.state != "Infected":
        continue

      for neighbor_id in neighbors:

        neighbor = self.people[neighbor_id]

        if neighbor.state == "Infected":
          continue

        if random.random() < self._effective_probability(person, neighbor):
          newly_infected.add(neighbor_id)

    # 가정 내 전파는 비가정 접촉 간선과 별도로 계산한다.
    # 일별 위험을 재분배해 한 가구원에 대한 누적 기준 위험을 28%로 맞춘다.
    for infected in self.people.values():
      if infected.state != "Infected" or infected.infected_at_hour is None:
        continue

      age_day = (self.total_hours - infected.infected_at_hour) // 24
      daily_probability = self._household_daily_probability(infected, age_day)
      if daily_probability <= 0:
        continue

      home = self.person_locations[infected.ID]["home"]
      for neighbor_id in home.people:
        neighbor = self.people[neighbor_id]
        if neighbor.ID == infected.ID or neighbor.state == "Infected":
          continue

        probability = daily_probability
        if neighbor.vaccine:
          # 접종 효과는 실제 전파 확률에 반영되는 중요한 면역 보정이다.
          probability *= 1 - self.vaccine_effectiveness
        if neighbor.state == "Recovered":
          probability *= 1 - self.recovered_probability
        if random.random() < probability:
          newly_infected.add(neighbor.ID)

    # 모든 판정을 마친 뒤 상태를 일괄 변경해, 같은 날 새 감염자가 즉시 전파하지 않게 한다.
    # 회복 시각도 난수로 정하므로 사람 ID 순서로 처리해 실행 결과를 재현 가능하게 한다.
    for person_id in sorted(newly_infected):
      person = self.people[person_id]
      # 23시 판정 직후 자정으로 넘어가므로 다음 시각을 감염 시점으로 기록한다.
      self._mark_infected(person, self.total_hours + 1)

    # 감염자가 전체 인원의 절반 이상이면 거리두기를 활성화한다.
    infected_count = self.infected_count()

    if infected_count >= len(self.people) * 0.5:
      self.is_distancing_active = True

    return True


  def simulate_hour(self) -> bool:
    # 매시간: 회복 확인 → 카페 그룹 배정 → 이동 → 접촉 기록.
    self.recovered_check()
    self._assign_cafe_groups()

    for person in self.people.values():
      person.move(self.hour)

    self.contact_check()

    # 접촉 간선을 하루 동안 모은 뒤 23시에 하루치 감염 판정을 한 번 실행한다.
    if self.hour == 23:
      self.infection_phase()
    self.hour += 1
    self.total_hours += 1

    if self.hour >= 24:
      self.hour = 0
      self._daily_pairs.clear()
      self.graph = {person_id: [] for person_id in self.people}

    return True


  def _assign_cafe_groups(self) -> None:
    # 매시간 카페 그룹을 재구성하므로 이전 시간의 점유 목록을 비운다.
    # 그래야 새 그룹으로 이동할 때 아직 떠나지 않은 사람 때문에 집으로 잘못 이동하지 않는다.
    for group in self.locations["cafe"]:
      group.people.clear()

    # 방문자를 무작위로 섞어 2명 이하인 임시 그룹들에 나눈다.
    visitors = [
        person for person in self.people.values()
        if person.schedule.get(self.hour) is self.person_locations[person.ID]["cafe"]
    ]

    random.shuffle(visitors)
    groups = self.locations["cafe"]

    for index, person in enumerate(visitors):
      person.schedule[self.hour] = groups[index // self.GROUP_SIZES["cafe"]]


  def simulate_day(self) -> bool:
    # 24시간을 진행하고 하루가 끝났을 때 감염자 수를 결과에 기록한다.
    for _ in range(24):
      self.simulate_hour()

    self.result = pd.concat([
        self.result,
        pd.DataFrame({"day": [self.day], "infected": [self.infected_count()]}),
    ], ignore_index=True)

    self.day += 1
    # 다음 날 일정을 새로 만들며, 감염자의 격리 추첨도 이 시점에 이뤄진다.
    for person in self.people.values():
      person.schedule = self.create_schedule(person)

    return True


  def run(self, days: int) -> bool:
    # 요청한 일수만큼 시뮬레이션하고 결과 조회를 위해 날짜를 인덱스로 설정한다.
    if days < 0:
      raise ValueError("days must be non-negative")

    for _ in range(days):
      self.simulate_day()

    self.result.set_index("day", inplace=True)

    return True
