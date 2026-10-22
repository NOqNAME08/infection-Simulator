import sys


class Location:

  def __init__(self, name: str, limit: int = sys.maxsize):
    if not isinstance(limit, int) or limit <= 0:
      raise ValueError("limit must be a positive integer")

    self.name = name
    self.people : list[int] = [] #it has ID of the person
    self.people_limit : int = limit
