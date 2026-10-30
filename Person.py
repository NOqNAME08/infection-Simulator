from Location import Location


class Person:

  def __init__(self,
      id: int,
      schedule: dict[int, Location],
      occupation: str,
  ) -> None:
    # ID는 시뮬레이션 안에서 사람을 구분하는 고유 번호다.
    self.id = id
    # schedule은 시각(0~23)에서 해당 시각의 Location으로 연결된다.
    self.schedule = schedule
    # occupation은 낮 시간의 기본 소속 장소(school 또는 company)를 정한다.
    self.occupation = occupation
    self.vaccine = False
    self.cur_location: Location | None = None
    # 감염이 발생한 장소와 시각. 전파 경과 시간은 infected_at_hour로 계산한다.
    self.infected_at: Location | None = None
    self.infected_at_hour: int | None = None
    # 감염 후 증상 발현과 회복/사망 예정 시각을 기록한다.
    self.symptom_onset_at_hour: int | None = None
    self.outcome_at_hour: int | None = None
    self.outcome_duration_days: int | None = None
    self.next_death_check_at_hour: int | None = None
    self.daily_death_probability: float | None = None
    # 회복 직후부터 면역 효과가 감소하는 기준 시각과 감염 에피소드 수.
    self.recovered_at_hour: int | None = None
    self.infection_count: int = 0
    # 격리 여부는 감염 상태와 별도 관리해 Safe/Recovered 상태를 늘리지 않는다.
    self.is_isolated: bool = False
    self.state : str = "Safe"
    # state의 허용 값: Safe, Exposed, Infected(증상 발현), Recovered, Dead.


  def move(self, time) -> str:
    # 현재 위치가 정해지지 않은 사람은 이동할 수 없다.
    if self.cur_location is None:
      raise Exception("No location")

    # 해당 시각의 목적지를 읽고, 수용인원을 초과하면 집으로 돌린다.
    destination = self.schedule[time]

    # 목적지가 가득 찼으면 집으로 이동한다.
    if (
        destination is not self.cur_location
        and len(destination.people) >= destination.people_limit
    ):
      # 일정에 등록된 home 장소를 찾아 대체 목적지로 사용한다.
      home = next(
          (location for location in self.schedule.values()
           if location.name.startswith("home_")),
          None,
      )
      if home is None:
        raise ValueError("schedule must include a home location")
      destination = home

    if destination is not self.cur_location:
      # 기존 장소에서 사람 ID를 제거한 다음 새 장소로 이동한다.
      if self.id in self.cur_location.people:
        self.cur_location.people.remove(self.id)
      self.cur_location = destination

    # 현재 위치의 인원 목록에 본인이 정확히 포함되도록 보정한다.
    if self.id not in self.cur_location.people:
      self.cur_location.people.append(self.id)

    return f"{self.id} this person is moved to {self.cur_location.name}"
