import random
import pandas as pd

import Location
import Person


class Simulation:

  def __init__(self):

    self.result : pd.DataFrame = pd.DataFrame(columns=["day", "infected"])

    self.people : dict[int, Person.Person] = {}    # 0 : person(...), 1 : person(...)
    self.graph : dict[int, list[int]] = {}         # 하루 하루 초기화 중.

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
    self.infection_probability : float = 0.15 #감염율
    self.vaccine_effectiveness : float = 0.70 #백신 효과 (100퍼가 아님)
    self.recovered_probability : float = 0.85

  def infected_count(self):
    infected_count = sum(
        person.state == "Infected"
        for person in self.people.values()
    )
    return infected_count

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

      #초기 백신 접종자
      if random.random() < 0.4:
        self.people[person_id].vaccine = True

      # 초기에는 접촉 관계가 없는 빈 그래프
      self.graph[person_id] = []


    # 초기 감염자 한 명 지정
    initial_infected = random.choice(list(self.people.values()))
    initial_infected.state = "Infected"

    return True


  # 모든 사람들을 검사.
  def recovered_check(self):
    people = self.people.values()
    for person in people :
      #date가 None인 경우 에러 발생. 미리 처리.
      if person.infected_date is None:
        continue
      if int(self.total_hours/24) - person.infected_date >= 7 :
        person.infected_date = None
        person.state = "Recovered"
        person.infected_at = None


  def contact_check(self) -> None:
    # 초기 셋업.
    self.graph = {
        person_id : []
        for person_id in self.people
    }
    # 모든 위치에 대하여 사람들의 접촉 여부를 판별
    for location in self.locations.values() :
      if location.name == "home" :
        continue
      people_here = location.people
      # 사람 둘을 뽑아 둘의 접촉율을 테스트 및 그래프에 반영
      for i in range(len(people_here)) :
        person_a = people_here[i]

        for j in range(i + 1, len(people_here)) :
          person_b = people_here[j]

          # 두 사람이 직접 접촉할 확률 (일시적 값)
          if random.random() < 0.015 :
            self.graph[person_a].append(person_b)
            self.graph[person_b].append(person_a)


  def infection_phase(self) -> bool:
    newly_infected: set[int] = set()
    # 접촉한 사람들을 대상으로 감염 여부를 제공
    for person_id, neighbors in self.graph.items():
        person = self.people[person_id]

        if not person.state == "Infected" :
            continue
        #전체 반복
        for neighbor_id in neighbors:
            neighbor = self.people[neighbor_id]
            #감염된 경우 제거
            if neighbor.state == "Infected" :
                continue
            # 감염율 값 받아오기.(상수 변화 최소화)
            probability = self.infection_probability

            # 백신 접종자는 감염 확률 감소
            if neighbor.vaccine:
              probability *= (1 - self.vaccine_effectiveness)
            # 회복자는 감염 확률 감소
            if neighbor.state == "Recovered" :
              probability *= (1 - self.recovered_probability)

            if random.random() < probability:
                newly_infected.add(neighbor_id)

    # 모든 감염 판정이 끝난 뒤 상태 변경
    for person_id in newly_infected:
        self.people[person_id].state = "Infected"
        self.people[person_id].infected_at = self.people[person_id].cur_location
        self.people[person_id].infected_date = self.day

    # 감염자 비율이 50% 이상이면 거리두기 발령
    infected_count = sum(
        person.state == "Infected"
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
    self.recovered_check()
    self.hour += 1
    self.total_hours += 1

    if self.hour >= 24 :
      self.hour = 0

    return True


  def simulate_day(self) -> bool :
    for _ in range(24) :
      self.simulate_hour()

    data = {
      "day" : [self.day],
      "infected" : [self.infected_count()]
    }
    temp = pd.DataFrame(data)

    self.result = pd.concat([self.result, temp], ignore_index = True)

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

    self.result.set_index("day", inplace = True)
    return True