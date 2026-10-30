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
    self.result: pd.DataFrame = pd.DataFrame(columns=[
        "day", "susceptible", "exposed", "symptomatic", "infected",
        "recovered", "dead", "cumulative_infected", "infection_events",
        "reinfections", "initial_cases", "external_imports", "local_infections",
        "recovery_events", "death_events", "resolved_cases", "resolved_death_rate",
    ])
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
    # 회복 직후 면역 보호 효과는 85%이며, 반감기마다 남은 효과가 절반으로 감소한다.
    self.recovered_immunity_half_life_days: float = 180.0
    # 외부에서 새로 들어오는 감염 시도 수의 평균(인구 1,000명·하루 기준).
    # 지역 자료에 맞춰 조정해야 하는 실험 시작값이다.
    self.importation_rate_per_1000_per_day: float = 0.1
    # 잠복기는 2~4일 범위이며 삼각분포의 최빈값을 4일로 둬 긴 쪽에 무게를 준다.
    self.incubation_min_hours: int = 2 * 24
    self.incubation_max_hours: int = 4 * 24
    self.incubation_mode_hours: int = 4 * 24
    # 증상 발현 뒤 13~17일 사이에 회복하거나 사망하도록 개인별 기간을 정한다.
    self.symptom_to_outcome_min_days: int = 13
    self.symptom_to_outcome_max_days: int = 17
    # 전체 질병 기간 동안 매일 사망 판정을 했을 때의 누적 목표 확률이다.
    self.target_cumulative_death_probability: float = 0.12
    self.isolation_probability: float = 0.40  # 감염자의 격리 일정 생성 확률
    # 하루 중 접촉 간선 생성을 이미 추첨한 사람 쌍. 간선은 하루 동안 유지한다.
    self._daily_pairs: set[tuple[int, int]] = set()
    # 감염 기간 길이별 가정 전파 가중치 합을 캐시해 시간별 계산을 줄인다.
    self._household_weight_sums: dict[int, float] = {}
    # 재감염 시에도 과거에 끝난 질병 에피소드의 결과 비율을 유지한다.
    self.recovery_events: int = 0
    self.death_events: int = 0
    self.external_import_events: int = 0
    self.initial_seed_events: int = 0


  @staticmethod
  def infectivity_curve(age_hours: int, duration_hours: int = 17 * 24) -> float:
    """감염 경과 기간 끝에서 0이 되는 비대칭 포물선 감염력 곡선."""
    peak_hour = round(3.5 * 24)
    if age_hours < 0 or age_hours >= duration_hours or duration_hours <= peak_hour:
      return 0.0
    if age_hours <= peak_hour:
      # 감염 시점에는 0, 3.5일째에는 1이 되도록 증가한다.
      return 1.0 - ((peak_hour - age_hours) / peak_hour) ** 2
    # 긴 꼬리 구간으로 나눠 3.5일 이후의 하강 기울기 절대값을 낮춘다.
    return 1.0 - ((age_hours - peak_hour) / (duration_hours - peak_hour)) ** 2


  @staticmethod
  def _daily_death_probability(days_until_outcome: int, target_probability: float) -> float:
    """매일 동일한 사망 추첨을 했을 때 전체 누적 확률이 목표값이 되게 한다."""
    if days_until_outcome <= 0 or target_probability <= 0:
      return 0.0
    return 1.0 - (1.0 - target_probability) ** (1.0 / days_until_outcome)


  def _household_hourly_probability(
      self,
      infected: Person.Person,
      age_hours: int,
  ) -> float:
    """가정 전파 누적 위험 28%를 감염력 곡선에 따라 시간별로 나눈다."""
    if infected.infected_at_hour is None:
      return 0.0

    if infected.outcome_at_hour is None:
      return 0.0
    duration = infected.outcome_at_hour - infected.infected_at_hour
    if age_hours < 0 or age_hours >= duration:
      return 0.0

    if duration not in self._household_weight_sums:
      self._household_weight_sums[duration] = sum(
          self.infectivity_curve(hour, duration)
          for hour in range(duration)
      )
    weight_sum = self._household_weight_sums[duration]
    if weight_sum == 0:
      return 0.0

    weight = self.infectivity_curve(age_hours, duration)
    # 모든 감염 가능 시간의 위험을 합성하면 기준 누적 확률 28%가 된다.
    return 1.0 - (
        1.0 - self.household_transmission_probability
    ) ** (weight / weight_sum)


  @staticmethod
  def _make_groups(name: str, people_count: int, group_size: int):
    # 인구 규모를 수용할 수 있는 만큼 그룹을 만들고 마지막 그룹은 일부만 채운다.
    group_count = max(1, math.ceil(people_count / group_size))

    return [
        Location.Location(f"{name}_{index}", group_size)
        for index in range(group_count)
    ]


  def infected_count(self) -> int:
    # 잠복기와 증상 발현 상태를 모두 현재 감염자로 센다.
    return sum(
        person.state in {"Exposed", "Infected"}
        for person in self.people.values()
    )


  def _result_row(self) -> dict[str, int | float]:
    """일일 상태별 인원, 현재/누적 감염자, 확정 사례 중 사망 비율을 계산한다."""
    counts = {
        state: sum(person.state == state for person in self.people.values())
        for state in ("Safe", "Exposed", "Infected", "Recovered", "Dead")
    }
    resolved = self.recovery_events + self.death_events
    infection_events = sum(
        person.infection_count for person in self.people.values()
    )
    resolved_death_rate = self.death_events / resolved if resolved else float("nan")
    return {
        "day": self.day,
        "susceptible": counts["Safe"],
        "exposed": counts["Exposed"],
        "symptomatic": counts["Infected"],
        "infected": counts["Exposed"] + counts["Infected"],
        "recovered": counts["Recovered"],
        "dead": counts["Dead"],
        "cumulative_infected": len(self.people) - counts["Safe"],
        "infection_events": infection_events,
        "reinfections": infection_events - (len(self.people) - counts["Safe"]),
        "initial_cases": self.initial_seed_events,
        "external_imports": self.external_import_events,
        "local_infections": (
            infection_events
            - self.initial_seed_events
            - self.external_import_events
        ),
        "recovery_events": self.recovery_events,
        "death_events": self.death_events,
        "resolved_cases": resolved,
        "resolved_death_rate": resolved_death_rate,
    }


  def create_schedule(self, person: Person.Person) -> dict[int, Location.Location]:
    # 하루 일정을 만들 때 감염자의 격리 여부를 결정한다.
    home = self.person_locations[person.id]["home"]
    person_locations = self.person_locations[person.id]

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
    # 같은 시드와 같은 입력으로 재현 가능한 난수 흐름을 만든다. // 아직까진 실패
    if size <= 0:
      raise ValueError("size must be greater than 0")
    #초기화
    random.seed(random_seed)
    self.people.clear()
    self.graph.clear()
    self.person_locations.clear()
    self.day = self.hour = self.total_hours = 0
    self.is_distancing_active = False
    self.result = pd.DataFrame(columns=[
        "day", "susceptible", "exposed", "symptomatic", "infected",
        "recovered", "dead", "cumulative_infected", "infection_events",
        "reinfections", "initial_cases", "external_imports", "local_infections",
        "recovery_events", "death_events", "resolved_cases", "resolved_death_rate",
    ])
    self._daily_pairs.clear()
    self._household_weight_sums.clear()
    self.recovery_events = 0
    self.death_events = 0
    self.external_import_events = 0
    self.initial_seed_events = 0

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
      if random.random() < 0.0: # 임의의 값 현재는 0 퍼센트로 가정
        person.vaccine = True
      # 아직 접촉 간선이 없는 빈 인접 리스트를 만든다.
      self.graph[person_id] = []

    # 초기 감염자는 감염 사실을 아직 모르는 상태로 보고 일반 일정을 유지한다.
    # 이후 다음 날 일정을 만들 때 다른 감염자처럼 격리 여부를 추첨한다.
    initial_infected_count = max(1, size // 10)
    self.initial_seed_events = initial_infected_count

    for person in random.sample(list(self.people.values()), initial_infected_count):
      self._mark_infected(person, self.total_hours)

    return True


  def _mark_infected(self, person: Person.Person, infection_hour: int) -> None:
    """감염자를 잠복기로 전환하고 증상 발현 예정 시각을 정한다."""
    incubation_hours = round(random.triangular(
        self.incubation_min_hours,
        self.incubation_max_hours,
        self.incubation_mode_hours,
    ))
    outcome_days = random.randint(
        self.symptom_to_outcome_min_days,
        self.symptom_to_outcome_max_days,
    )
    person.state = "Exposed"
    person.infected_at = person.cur_location
    person.infected_at_hour = infection_hour
    person.symptom_onset_at_hour = infection_hour + incubation_hours
    person.outcome_duration_days = outcome_days
    person.outcome_at_hour = (
        person.symptom_onset_at_hour + outcome_days * 24
    )
    person.next_death_check_at_hour = None
    person.daily_death_probability = None
    person.recovered_at_hour = None
    person.infection_count += 1
    person.is_isolated = False


  def _recovered_protection(self, person: Person.Person) -> float:
    """회복 직후 보호 효과가 반감기마다 절반으로 감소하는 값을 반환한다."""
    if person.state != "Recovered" or person.recovered_at_hour is None:
      return 0.0
    elapsed_days = max(0, self.total_hours - person.recovered_at_hour) / 24
    half_life = max(self.recovered_immunity_half_life_days, 1e-9)
    return self.recovered_probability * 0.5 ** (elapsed_days / half_life)


  @staticmethod
  def _sample_poisson(expected_count: float) -> int:
    """일일 외부 유입 건수를 평균값에 맞춰 확률적으로 추출한다."""
    if expected_count <= 0:
      return 0
    if expected_count >= 30:
      # 큰 평균에서는 정규 근사로 계산량을 제한한다.
      return max(0, round(random.gauss(expected_count, math.sqrt(expected_count))))

    threshold = math.exp(-expected_count)
    product = 1.0
    count = 0
    while product > threshold:
      count += 1
      product *= random.random()
    return count - 1


  def _introduce_external_cases(self) -> int:
    """하루 단위 외부 감염 시도를 만들고 백신·회복 면역을 반영한다."""
    expected = (
        self.importation_rate_per_1000_per_day
        * len(self.people)
        / 1000
    )
    import_count = self._sample_poisson(expected)
    if import_count <= 0:
      return 0

    candidates = [
        person for person in self.people.values()
        if person.state in {"Safe", "Recovered"}
    ]
    random.shuffle(candidates)
    introduced = 0
    for person in candidates:
      if introduced >= import_count:
        break
      susceptibility = 1.0
      if person.vaccine:
        susceptibility *= 1 - self.vaccine_effectiveness
      if person.state == "Recovered":
        susceptibility *= 1 - self._recovered_protection(person)
      if random.random() < susceptibility:
        self._mark_infected(person, self.total_hours)
        introduced += 1
    return introduced


  def disease_progression_check(self) -> None:
    # 매시간 잠복기 종료와 증상 발현 후 회복/사망 여부를 확인한다.
    for person in self.people.values():
      if (
          person.state == "Exposed"
          and person.symptom_onset_at_hour is not None
          and self.total_hours >= person.symptom_onset_at_hour
      ):
        person.state = "Infected"
        days_until_outcome = person.outcome_duration_days
        if days_until_outcome is None:
          raise ValueError("infected person is missing outcome duration")
        person.daily_death_probability = self._daily_death_probability(
            days_until_outcome,
            self.target_cumulative_death_probability,
        )
        person.next_death_check_at_hour = self.total_hours + 24

      if (
          person.state == "Infected"
          and person.outcome_at_hour is not None
          and person.next_death_check_at_hour is not None
          and self.total_hours >= person.next_death_check_at_hour
      ):
        if (
            person.daily_death_probability is not None
            and random.random() < person.daily_death_probability
        ):
          person.state = "Dead"
          self.death_events += 1
          if person.cur_location is not None and person.id in person.cur_location.people:
            person.cur_location.people.remove(person.id)
          person.cur_location = None
          person.next_death_check_at_hour = None
        elif self.total_hours >= person.outcome_at_hour:
          person.state = "Recovered"
          person.recovered_at_hour = self.total_hours
          self.recovery_events += 1
          person.schedule = self.create_schedule(person)
          person.next_death_check_at_hour = None
        else:
          person.next_death_check_at_hour += 24

        person.is_isolated = False


  def contact_check(self) -> None:
    # 매시간 현재 같은 비가정 장소에 있는 쌍을 살핀다.
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
          # 접촉 간선은 하루에 한 번만 추첨하고, 성공한 간선은 그날 유지한다.

          if pair in self._daily_pairs:
            continue

          self._daily_pairs.add(pair)

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
    duration = (
        person.outcome_at_hour - person.infected_at_hour
        if person.outcome_at_hour is not None and person.infected_at_hour is not None
        else self.symptom_to_outcome_max_days * 24
    )
    probability = self.infection_probability * self.infectivity_curve(age, duration)

    if neighbor.vaccine:
      probability *= 1 - self.vaccine_effectiveness

    if neighbor.state == "Recovered":
      probability *= 1 - self._recovered_protection(neighbor)

    return probability


  def infection_phase(self) -> bool:
    # 현재 시간에 접촉 중인 간선과 가구원을 대상으로 감염을 판정한다.
    newly_infected: set[int] = set()

    for person_id, neighbors in self.graph.items():
      person = self.people[person_id]

      if person.state not in {"Exposed", "Infected"}:
        continue

      for neighbor_id in neighbors:

        neighbor = self.people[neighbor_id]

        if neighbor.state in {"Exposed", "Infected", "Dead"}:
          continue
        # 오늘 만들어진 간선이라도 현재 같은 장소에 있을 때만 전파를 시도한다.
        if person.cur_location is not neighbor.cur_location:
          continue
        if person.cur_location is None or person.cur_location.name.startswith("home_"):
          continue

        if random.random() < self._effective_probability(person, neighbor):
          newly_infected.add(neighbor_id)

    # 가정 내 누적 위험 28%를 감염력 곡선에 따라 시간별 위험으로 나눈다.
    for infected in self.people.values():
      if infected.state not in {"Exposed", "Infected"} or infected.infected_at_hour is None:
        continue

      age_hours = self.total_hours - infected.infected_at_hour
      hourly_probability = self._household_hourly_probability(infected, age_hours)
      if hourly_probability <= 0:
        continue

      home = self.person_locations[infected.id]["home"]
      # 가정 전파는 감염자도 실제로 집에 있는 시간에만 판정한다.
      if infected.cur_location is not home:
        continue

      for neighbor_id in home.people:
        neighbor = self.people[neighbor_id]
        if neighbor.id == infected.id or neighbor.state in {"Exposed", "Infected", "Dead"}:
          continue

        probability = hourly_probability
        if neighbor.vaccine:
          # 접종 효과는 실제 전파 확률에 반영되는 중요한 면역 보정이다.
          probability *= 1 - self.vaccine_effectiveness
        if neighbor.state == "Recovered":
          probability *= 1 - self._recovered_protection(neighbor)
        if random.random() < probability:
          newly_infected.add(neighbor.id)

    # 해당 시간의 모든 판정을 마친 뒤 상태를 일괄 변경해 같은 시간 연쇄 전파를 막는다.
    # 회복 시각도 난수로 정하므로 사람 ID 순서로 처리해 실행 결과를 재현 가능하게 한다.
    for person_id in sorted(newly_infected):
      person = self.people[person_id]
      # 현재 시간의 접촉 판정 직후를 감염 시점으로 기록한다.
      self._mark_infected(person, self.total_hours + 1)

    # 감염자가 전체 인원의 절반 이상이면 거리두기를 활성화한다.
    infected_count = self.infected_count()

    if infected_count >= len(self.people) * 0.5:
      self.is_distancing_active = True

    return True


  def simulate_hour(self) -> bool:
    # 매시간: 회복 확인 → 카페 그룹 배정 → 이동 → 접촉 생성 → 전파 판정.
    self.disease_progression_check()
    self._assign_cafe_groups()

    for person in self.people.values():
      if person.state == "Dead":
        continue
      person.move(self.hour)

    self.contact_check()
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
        if person.schedule.get(self.hour) is self.person_locations[person.id]["cafe"]
    ]

    random.shuffle(visitors)
    groups = self.locations["cafe"]

    for index, person in enumerate(visitors):
      person.schedule[self.hour] = groups[index // self.GROUP_SIZES["cafe"]]


  def simulate_day(self) -> bool:
    # 매일 외부 유입을 추첨하고 24시간을 진행한 뒤 결과를 기록한다.
    self.external_import_events += self._introduce_external_cases()
    for _ in range(24):
      self.simulate_hour()

    self.result = pd.concat([
        self.result,
        pd.DataFrame([self._result_row()]),
    ], ignore_index=True)

    self.day += 1
    # 다음 날 일정을 새로 만들며, 감염자의 격리 추첨도 이 시점에 이뤄진다.
    for person in self.people.values():
      if person.state == "Dead":
        continue
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
