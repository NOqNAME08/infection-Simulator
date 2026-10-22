from Location import Location


class Person:

  def __init__(self,
      ID: int,
      schedule: dict[int, Location],
      occupation: str,
  ) -> None:
    self.ID = ID
    self.schedule = schedule
    self.occupation = occupation
    self.vaccine = False
    self.cur_location: Location | None = None
    self.infected_at: Location | None = None
    self.infected_at_hour: int | None = None
    self.is_isolated: bool = False
    self.state : str = "Safe"
    """Safe, Infected, or Recovered."""


  def move(self, time) -> str:
    #cur_loc의 예외
    if self.cur_location is None:
      raise Exception("No location")

    destination = self.schedule[time]

    # 목적지가 가득 찼으면 집으로 이동한다.
    if (
        destination is not self.cur_location
        and len(destination.people) >= destination.people_limit
    ):
      home = next( # next는 iteral 타입에서 다음을 가져옴 return해 줌.
          (location for location in self.schedule.values()
           if location.name == "home"),
          None,
      )
      if home is None:
        raise ValueError("schedule must include a home location")
      destination = home

    if destination is not self.cur_location:
      # 이전 위치에서 나간 뒤 목적지로 이동
      if self.ID in self.cur_location.people:
        self.cur_location.people.remove(self.ID)
      self.cur_location = destination

    # 현재 위치의 인원 목록이 일관되도록 유지
    if self.ID not in self.cur_location.people:
      self.cur_location.people.append(self.ID)

    return f"{self.ID} this person is moved to {self.cur_location.name}"
