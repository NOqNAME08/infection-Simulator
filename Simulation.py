import random

import Location
import Person


class Simulation:

  def __init__(self):

    self.people : dict[int, Person.Person] = {}    # 0 : person(...), 1 : person(...)
    self.graph : dict[int, list[int]] = {}

    self.locations : dict[str, Location.Location] = {
      'cafe' : Location.Location('cafe'),
      'school' : Location.Location('school'),
      'academy' : Location.Location('academy'),
      'company' : Location.Location('company'),
      'home' : Location.Location('home')
    }

    self.day : int = 0
    self.hour : int = 0
    self.total_hours : int = 0 #누적 값.
    self.is_distancing_active: bool = False
    self.occupations: dict[int, str] = {}
    self.infection_probability: float = 0.15 #감염율
    self.vaccine_effectiveness: float = 0.70 #백신 효과 (100퍼가 아님)


  def create_schedule(self, occupation: str) -> dict[int, Location.Location]:

    home = self.locations["home"]

    schedule = {hour: home for hour in range(24)}

    for hour in range(9, 17):
      if self.is_distancing_active and random.random() < 0.5:
        schedule[hour] = home
      else:
        schedule[hour] = self.locations[occupation]

    attends_academy = (
        occupation == "school"
        and random.random() < 0.4
    )

    for hour in range(17, 21):
      if attends_academy and hour < 20:
        schedule[hour] = self.locations["academy"]
      elif (
          not self.is_distancing_active
          and random.random() < 0.3
      ):
        schedule[hour] = self.locations["cafe"]
      else:
        schedule[hour] = home

    return schedule


  def setup(self, size: int = 100) -> bool:

    if size <= 0:
      raise ValueError("size must be greater than 0")

    #재시작 시 초기화
    self.people.clear()
    self.graph.clear()
    self.occupations.clear()

    for location in self.locations.values():
      location.people.clear()

    self.day = 0
    self.hour = 0
    self.total_hours = 0
    self.is_distancing_active = False

    #직업 선택과 스케쥴 제작
    for person_id in range(size):
      occupation = random.choice(["school", "company"])
      self.occupations[person_id] = occupation

      schedule = self.create_schedule(occupation)

      person = Person.Person(
          ID=person_id,
          schedule=schedule
      )

      # 0시의 초기 위치는 집
      person.cur_location = self.locations["home"]
      person.cur_location.people.append(person_id)

      self.people[person_id] = person

      # 초기에는 접촉 관계가 없는 빈 그래프
      self.graph[person_id] = []

    # 초기 감염자 한 명 지정
    initial_infected = random.choice(list(self.people.values()))
    initial_infected.infection = True

    return True


  def contact_check(self) -> None:
    # 초기 셋업.
    self.graph = {
        person_id : []
        for person_id in self.people
    }

    for location in self.locations.values() :
      people_here = location.people

      for i in range(len(people_here)) :
        person_a = people_here[i]

        for j in range(i + 1, len(people_here)) :
          person_b = people_here[j]

          # 두 사람이 직접 접촉할 확률 (일시적 값)
          if random.random() < 0.1 :
            self.graph[person_a].append(person_b)
            self.graph[person_b].append(person_a)


  def infection_phase(self) -> bool:
    newly_infected: set[int] = set()

    for person_id, neighbors in self.graph.items():
        person = self.people[person_id]

        if not person.infection:
            continue

        for neighbor_id in neighbors:
            neighbor = self.people[neighbor_id]

            if neighbor.infection:
                continue

            probability = self.infection_probability

            # 백신 접종자는 감염 확률 감소
            if neighbor.vaccine:
                probability *= (1 - self.vaccine_effectiveness)

            if random.random() < probability:
                newly_infected.add(neighbor_id)

    # 모든 감염 판정이 끝난 뒤 상태 변경
    for person_id in newly_infected:
        self.people[person_id].infection = True

    # 감염자 비율이 50% 이상이면 거리두기 발령
    infected_count = sum(
        person.infection
        for person in self.people.values()
    )

    if infected_count >= len(self.people) * 0.5:
        self.is_distancing_active = True

    return True

  def simulate_hour(self) -> bool :
    for person in self.people.values() :
      person.move(self.hour)

    self.contact_check()
    self.infection_phase()
    self.hour += 1
    self.total_hours += 1

    if self.hour >= 24 :
      self.hour = 0

    return True

  def simulate_day(self) -> bool :
    for _ in range(24) :
      self.simulate_hour()

    self.day += 1

    # 다음 날 스케줄 생성
    for person_id, person in self.people.items() :
      occupation = self.occupations[person_id]
      person.schedule = self.create_schedule(occupation)

    return True

  def run(self, days: int) -> bool :
    if days < 0 :
      raise ValueError("days must be non-negative")

    for _ in range(days) :
      self.simulate_day()

    return True