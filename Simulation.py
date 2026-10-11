import random

import Location
import Person


class Simulation:

  def __init__(self):

    self.people : dict[int, Person.Person] = {}    # 0 : person(...), 1 : person(...)
    self.graph : dict[int, list[list[int]]] = {}

    self.locations : dict[str, Location.Location] = {
      'cafe' : Location.Location('cafe'),
      'school' : Location.Location('school'),
      'academy' : Location.Location('academy'),
      'company' : Location.Location('company'),
      'home' : Location.Location('home')
    }

    self.day : int = 0
    self.hour : int = 0
    self.is_distancing_active: bool = False


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

    for location in self.locations.values():
      location.people.clear()

    self.day = 0
    self.hour = 0

    #직업 선택과 스케쥴 제작
    for person_id in range(size):
      occupation = random.choice(["school", "company"])

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

    for person_id in range(len(self.people)):
      if self.graph[person_id] is None:
        self.graph[person_id] = []

      temp:list[int]  = []
      for id in self.people[person_id].cur_location.people:
        temp.append(id)
      self.graph[person_id].append(temp)


  def infection_phase(self) -> bool:
    #TODO


    #감염 정도를 확인하고 감염자가 특정 값 이상으로 많을 시 거리두기 조치
    count: int = 0
    for person in self.people.values():
      if person.infection:
        count += 1

    if count >= len(self.people)*0.5:
      self.is_distancing_active = True

    return True


  def simulate_hour(self) -> bool:

    while self.hour < 24:
      for person in self.people.values():
        person.move(self.hour)

      self.contact_check()

      self.hour += 1

    self.hour = 0

    return True


  def simulate_day(self) -> bool:
    #TODO
    for person in self.people.values():

      occupation = random.choice(["school", "company"])
      person.schedule = self.create_schedule(occupation)

    self.infection_phase()
    return True


  def run(self, days) -> bool:
    #TODO
    for i in range(days):
      self.simulate_day()

    return True