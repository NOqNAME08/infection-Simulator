import sys


class Location:

  def __init__(self, name: str, limit: int = sys.maxsize):
    # 그룹 크기는 양의 정수여야 한다.
    if not isinstance(limit, int) or limit <= 0:
      raise ValueError("limit must be a positive integer")

    # name은 장소 유형과 그룹 번호를 식별하고, people은 현재 체류 중인 ID를 담는다.
    self.name = name
    self.people : list[int] = []
    # people_limit은 이 소그룹에 동시에 들어갈 수 있는 최대 인원이다.
    self.people_limit : int = limit
