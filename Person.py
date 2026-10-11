from Location import Location

class Person:
  # ID        : int
  # infection : bool #감염
  # isolated  : bool #격리
  # vaccine   : bool #백신
  # schedule  : dict[int, Location]
  # cur_location : Location

  def __init__(self,
      ID: int,
      schedule: dict[int, Location],
  ) -> None:
    self.ID = ID
    self.schedule = schedule
    self.infection = False
    self.vaccine = False
    self.isolated = False

  def move(self, time) -> str:
    #격리
    if self.isolated:
      return f"{self.ID} : this person is isolated"
    #cur_loc의 예외
    if self.cur_location is None:
      raise Exception("No location")

    if self.ID in self.cur_location.people:
      self.cur_location.people.remove(self.ID)

    self.cur_location = self.schedule[time]

    if self.ID not in self.cur_location.people:
      self.cur_location.people.append(self.ID)

    return f"{self.ID} this person is moved to {self.cur_location.name}"