from Location import Location


class Person:

  def __init__(self,
      ID: int,
      schedule: dict[int, Location],
  ) -> None:
    self.ID = ID
    self.schedule = schedule
    self.vaccine = False
    self.cur_location: Location | None = None
    self.infected_at: int | None = None
    self.infected_date: int | None = None
    self.state : str = "Safe"
    """Safe, Infected, Recovered, Isolated"""


  def move(self, time) -> str:
    #격리
    if self.state == "Isolated":
      return f"{self.ID} : this person is isolated"
    #cur_loc의 예외
    if self.cur_location is None:
      raise Exception("No location")

    # 이전 위치 삭제
    if self.ID in self.cur_location.people:
      self.cur_location.people.remove(self.ID)
    # 현재 위치 설정
    self.cur_location = self.schedule[time]
    # 현재 위치의 인원 증가
    if self.ID not in self.cur_location.people:
      self.cur_location.people.append(self.ID)

    return f"{self.ID} this person is moved to {self.cur_location.name}"