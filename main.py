# II. 이론적 배경
# 그래프 이론: 개체(노드, Node)와 개체 간의 관계(간선, Edge)를 연결하여 네트워크 구조를 분석하는 이산수학 분야.
#
# 파이썬의 객체지향과 자료구조:
#
# Person 클래스를 활용해 상태값(감염 여부, 백신 여부)을 가진 개체를 생성.
#
# dict와 list를 활용해 그래프의 인접 리스트(Adjacency List) 구현.
#
# person : PK, 감염 여부, 백신 여부
# 접촉여부 : graph로
# routine : day 단위의 행동 양식. random
# 감염확률 : random
# 전파 알고리즘 : DFS, BFS, 몬테 카를로 시뮬레이터(확률적 반복 탐색), ABM(Agent-Based Modeling), 다익스트라(최단 시간)
# ABM 방식 채택.
#
# 실험 1: 백신 접종률 변화 (0% vs 30% vs 70%)
# 시간대별 이동 로직 (행동 규칙)
#     if 9 <= hour < 17:
#       # 낮 시간: 학교/회사로 이동 (거리두기 발령 시 50% 확률로 재택)
#       if is_distancing_active and random.random() < 0.5:
#         self.current_location = self.home
#       else:
#         self.current_location = self.school
#     elif 17 <= hour < 21:
#       # 저녁 시간: 30% 확률로 카페 방문, 아니면 귀가
#       if not is_distancing_active and random.random() < 0.3:
#         self.current_location = cafe_location
#       else:
#         self.current_location = self.home
#     else:
#       # 밤/새벽 시간: 귀가
#       self.current_location = self.home
#
# 분석: 백신 접종자가 네트워크 중간 길목(연결도가 높은 노드)에 위치할수록 전파가 차단되는 '집단면역(Herd Immunity)' 효과가 현저히 드러남.
#
# 실험 2: 사회적 거리두기(간선 축소)
#
# 분석: 노드 사이의 간선 수를 30% 줄였을 때, 바이러스가 전체 노드로 확산되는 데 걸리는 일수(Day)가 증가하여 확산 곡선이 평탄화됨(Flattening the curve).
#수요일 5시 과외로 변경.
from Simulation import Simulation

def main():
    simulation = Simulation()

    simulation.setup()
    # simulation.run(30)
    print("전체 인원:", len(simulation.people))
    print("초기 감염자:", [
        person.ID
        for person in simulation.people.values()
        if person.infection
    ])

    print("\n장소별 인원")
    for name, location in simulation.locations.items():
        print(name, len(location.people))

    person = simulation.people[0]
    print("\nPerson 0의 일정")
    for hour in range(24):
        print(hour, person.schedule[hour].name)

if __name__ == "__main__":
    main()