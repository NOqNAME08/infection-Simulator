import math
import random
import sys

import pandas as pd

import Location
import Person


class Simulation:

  GROUP_SIZES = {
      "school": 20,
      "company": 15,
      "cafe": 2,
      "academy": 10,
      "home": 4,
  }

  def __init__(self):
    self.result: pd.DataFrame = pd.DataFrame(columns=["day", "infected"])
    self.people: dict[int, Person.Person] = {}
    self.graph: dict[int, list[int]] = {}
    self.locations: dict[str, list[Location.Location]] = {}
    self.person_locations: dict[int, dict[str, Location.Location]] = {}

    self.day: int = 0
    self.hour: int = 0
    self.total_hours: int = 0
    self.is_distancing_active: bool = False
    self.infection_probability: float = 0.15
    self.contact_probability: float = 0.15
    self.household_transmission_probability: float = 0.28
    self.vaccine_effectiveness: float = 0.70
    self.recovered_probability: float = 0.85
    self.recovery_hours: int = 7 * 24
    self.isolation_probability: float = 0.40
    self._daily_pairs: set[tuple[int, int]] = set()
    self._home_pair_daily_probability = self._household_daily_probabilities()

  @staticmethod
  def infectivity_curve(age_hours: int) -> float:
    """Stylized quadratic infectivity curve, peaking at 3.5 days."""
    if age_hours < 0 or age_hours >= 7 * 24:
      return 0.0
    return max(0.0, 1.0 - ((age_hours - 84) / 84) ** 2)

  def _household_daily_probabilities(self) -> list[float]:
    weights = [self.infectivity_curve(day * 24 + 12) for day in range(7)]
    weight_sum = sum(weights)
    if weight_sum == 0:
      return [0.0] * 7
    return [
        1.0 - (1.0 - self.household_transmission_probability) ** (weight / weight_sum)
        for weight in weights
    ]

  @staticmethod
  def _make_groups(name: str, people_count: int, group_size: int):
    group_count = max(1, math.ceil(people_count / group_size))
    return [
        Location.Location(f"{name}_{index}", group_size)
        for index in range(group_count)
    ]

  def infected_count(self) -> int:
    return sum(person.state == "Infected" for person in self.people.values())

  def create_schedule(self, person: Person.Person) -> dict[int, Location.Location]:
    home = self.person_locations[person.ID]["home"]
    person_locations = self.person_locations[person.ID]

    if person.state == "Infected":
      if not person.is_isolated and random.random() < self.isolation_probability:
        person.is_isolated = True
      if person.is_isolated:
        return {hour: home for hour in range(24)}

    schedule = {hour: home for hour in range(24)}
    for hour in range(9, 17):
      if self.is_distancing_active and random.random() < 0.5:
        schedule[hour] = home
      else:
        schedule[hour] = person_locations[person.occupation]

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
    if size <= 0:
      raise ValueError("size must be greater than 0")
    random.seed(random_seed)
    self.people.clear()
    self.graph.clear()
    self.person_locations.clear()
    self.day = self.hour = self.total_hours = 0
    self.is_distancing_active = False
    self.result = pd.DataFrame(columns=["day", "infected"])
    self._daily_pairs.clear()
    self._home_pair_daily_probability = self._household_daily_probabilities()

    self.locations = {
        name: self._make_groups(name, size, group_size)
        for name, group_size in self.GROUP_SIZES.items()
    }
    home_groups = self.locations["home"]
    school_groups = self.locations["school"]
    company_groups = self.locations["company"]
    academy_groups = self.locations["academy"]

    occupations = [random.choice(["school", "company"]) for _ in range(size)]
    school_ids = [i for i, occupation in enumerate(occupations) if occupation == "school"]
    company_ids = [i for i, occupation in enumerate(occupations) if occupation == "company"]
    random.shuffle(school_ids)
    random.shuffle(company_ids)
    home_ids = list(range(size))
    random.shuffle(home_ids)

    assignment: dict[int, dict[str, Location.Location]] = {}
    for group_ids, groups, category in (
        (school_ids, school_groups, "school"),
        (company_ids, company_groups, "company"),
        (home_ids, home_groups, "home"),
    ):
      for position, person_id in enumerate(group_ids):
        assignment.setdefault(person_id, {})[category] = groups[position // self.GROUP_SIZES[category]]

    for position, person_id in enumerate(school_ids):
      assignment[person_id]["academy"] = academy_groups[
          position // self.GROUP_SIZES["academy"]
      ]
      assignment[person_id]["cafe"] = self.locations["cafe"][0]
    for person_id in company_ids:
      assignment[person_id]["cafe"] = self.locations["cafe"][0]

    for person_id, occupation in enumerate(occupations):
      person = Person.Person(person_id, {}, occupation)
      self.person_locations[person_id] = assignment[person_id]
      person.schedule = self.create_schedule(person)
      person.cur_location = assignment[person_id]["home"]
      person.cur_location.people.append(person_id)
      self.people[person_id] = person
      if random.random() < 0.4:
        person.vaccine = True
      self.graph[person_id] = []

    # Initial infections retain ordinary schedules until isolation is drawn
    # when the next schedule is generated.
    initial_infected_count = max(1, size // 20)
    for person in random.sample(list(self.people.values()), initial_infected_count):
      person.state = "Infected"
      person.infected_at_hour = self.total_hours
    return True

  def recovered_check(self) -> None:
    for person in self.people.values():
      if (
          person.state == "Infected"
          and person.infected_at_hour is not None
          and self.total_hours - person.infected_at_hour >= self.recovery_hours
      ):
        person.infected_at_hour = None
        person.state = "Recovered"
        person.infected_at = None
        person.is_isolated = False
        person.schedule = self.create_schedule(person)

  def contact_check(self) -> None:
    # Keep one sampled contact edge per person pair for the whole day.
    for location in {person.cur_location for person in self.people.values()}:
      if location is None or location.name.startswith("home_"):
        continue
      here = location.people
      for index, person_a in enumerate(here):
        for person_b in here[index + 1:]:
          pair = (min(person_a, person_b), max(person_a, person_b))
          if pair in self._daily_pairs:
            continue
          self._daily_pairs.add(pair)
          if random.random() < self.contact_probability:
            self.graph[pair[0]].append(pair[1])
            self.graph[pair[1]].append(pair[0])

  def _effective_probability(self, person: Person.Person, neighbor: Person.Person) -> float:
    infection_hour = person.infected_at_hour
    age = self.total_hours - (infection_hour if infection_hour is not None else self.total_hours)
    probability = self.infection_probability * self.infectivity_curve(age)
    if neighbor.vaccine:
      probability *= 1 - self.vaccine_effectiveness
    if neighbor.state == "Recovered":
      probability *= 1 - self.recovered_probability
    return probability

  def infection_phase(self) -> bool:
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

    # Home transmission is a separate episode-level 28% risk, distributed over
    # seven days using the same infectivity curve rather than the 15% edge draw.
    for infected in self.people.values():
      if infected.state != "Infected" or infected.infected_at_hour is None:
        continue
      age_day = (self.total_hours - infected.infected_at_hour) // 24
      if not 0 <= age_day < len(self._home_pair_daily_probability):
        continue
      home = self.person_locations[infected.ID]["home"]
      daily_probability = self._home_pair_daily_probability[age_day]
      for neighbor_id in home.people:
        neighbor = self.people[neighbor_id]
        if neighbor.ID == infected.ID or neighbor.state == "Infected":
          continue
        probability = daily_probability
        if neighbor.vaccine:
          probability *= 1 - self.vaccine_effectiveness
        if neighbor.state == "Recovered":
          probability *= 1 - self.recovered_probability
        if random.random() < probability:
          newly_infected.add(neighbor.ID)

    for person_id in newly_infected:
      person = self.people[person_id]
      person.state = "Infected"
      person.infected_at = person.cur_location
      person.infected_at_hour = self.total_hours
      person.is_isolated = False

    infected_count = self.infected_count()
    if infected_count >= len(self.people) * 0.5:
      self.is_distancing_active = True
    return True

  def simulate_hour(self) -> bool:
    self.recovered_check()
    self._assign_cafe_groups()
    for person in self.people.values():
      person.move(self.hour)
    self.contact_check()
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
    visitors = [
        person for person in self.people.values()
        if person.schedule.get(self.hour) is self.person_locations[person.ID]["cafe"]
    ]
    random.shuffle(visitors)
    groups = self.locations["cafe"]
    for index, person in enumerate(visitors):
      person.schedule[self.hour] = groups[index // self.GROUP_SIZES["cafe"]]

  def simulate_day(self) -> bool:
    for _ in range(24):
      self.simulate_hour()
    self.result = pd.concat([
        self.result,
        pd.DataFrame({"day": [self.day], "infected": [self.infected_count()]}),
    ], ignore_index=True)
    self.day += 1
    for person in self.people.values():
      person.schedule = self.create_schedule(person)
    return True

  def run(self, days: int) -> bool:
    if days < 0:
      raise ValueError("days must be non-negative")
    for _ in range(days):
      self.simulate_day()
    self.result.set_index("day", inplace=True)
    return True
