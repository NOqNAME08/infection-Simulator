"""
II. 이론적 배경
그래프 이론: 개체(노드, Node)와 개체 간의 관계(간선, Edge)를 연결하여 네트워크 구조를 분석하는 이산수학 분야.

파이썬의 객체지향과 자료구조:

Person 클래스를 활용해 상태값(감염 여부, 백신 여부)을 가진 개체를 생성.

dict와 list를 활용해 그래프의 인접 리스트(Adjacency List) 구현.

person : PK, 감염 여부, 백신 여부
접촉여부 : graph로
routine : day 단위의 행동 양식. random
감염확률 : random
전파 알고리즘 : DFS, BFS, 몬테 카를로 시뮬레이터(확률적 반복 탐색), ABM(Agent-Based Modeling), 다익스트라(최단 시간)
ABM 방식 채택.

실험 1: 백신 접종률 변화 (0% vs 30% vs 70%)
시간대별 이동 로직 (행동 규칙)
    if 9 <= hour < 17:
      # 낮 시간: 학교/회사로 이동 (거리두기 발령 시 50% 확률로 재택)
      if is_distancing_active and random.random() < 0.5:
        self.current_location = self.home
      else:
        self.current_location = self.school
    elif 17 <= hour < 21:
      # 저녁 시간: 30% 확률로 카페 방문, 아니면 귀가
      if not is_distancing_active and random.random() < 0.3:
        self.current_location = cafe_location
      else:
        self.current_location = self.home
    else:
      # 밤/새벽 시간: 귀가
      self.current_location = self.home

분석: 백신 접종자가 네트워크 중간 길목(연결도가 높은 노드)에 위치할수록 전파가 차단되는 '집단면역(Herd Immunity)' 효과가 현저히 드러남.

실험 2: 사회적 거리두기(간선 축소)

분석: 노드 사이의 간선 수를 30% 줄였을 때, 바이러스가 전체 노드로 확산되는 데 걸리는 일수(Day)가 증가하여 확산 곡선이 평탄화됨(Flattening the curve).
금요일 5시 과외로 변경.
"""

"""시뮬레이션을 실행하고 일별 감염자 수를 그래프로 표시한다."""

import datetime
import matplotlib.pyplot as plt
import random
import pandas as pd
from matplotlib.ticker import PercentFormatter

from Simulation import Simulation


# 그래프의 한글 제목/범례를 표시하고 음수 기호를 깨지지 않게 설정한다.
plt.rcParams["font.family"] = "Noto Sans CJK KR"
plt.rcParams["axes.unicode_minus"] = False


def main(num=100, day=5, seed: int = 0):
    print(datetime.datetime.now())
    # 실험 인원과 난수 시드를 전달해 초기 상태를 만든다.
    simulation = Simulation()
    simulation.setup(num, random_seed=seed)

    # 지정한 날짜 수만큼 진행한 뒤, 일별 감염자 수를 그린다.
    simulation.run(day)
    column_names = {
        "susceptible": "감염 가능",
        "exposed": "잠복기",
        "symptomatic": "증상 발현",
        "infected": "현재 감염자",
        "recovered": "회복",
        "dead": "사망",
        "cumulative_infected": "누적 감염자",
        "infection_events": "감염 에피소드",
        "reinfections": "재감염",
        "initial_cases": "초기 감염자",
        "external_imports": "외부 유입 감염",
        "local_infections": "지역 내 감염",
        "recovery_events": "누적 회복 사례",
        "death_events": "누적 사망 사례",
        "resolved_cases": "결과 확정 사례",
        "resolved_death_rate": "확정 사례 사망률",
    }
    result_ko = simulation.result.rename(columns=column_names)

    # 그래프와 같은 일별 결과를 한글 표로 터미널에도 출력한다.
    table = result_ko.copy()
    table.index.name = "일"
    table["확정 사례 사망률"] = table["확정 사례 사망률"].map(
        lambda value: f"{value:.1%}" if pd.notna(value) else "-"
    )
    print("\n[날짜별 시뮬레이션 결과]")
    print("감염 가능: 아직 감염되지 않은 인원 | 잠복기: 감염됐지만 증상 전인 인원")
    print("증상 발현: 증상이 있는 감염자 | 현재 감염자: 잠복기 + 증상 발현")
    print("누적 감염자: 현재 감염 + 회복 + 사망 | 확정 사례 사망률: 사망 / (회복 + 사망)")
    print("감염 에피소드: 첫 감염 + 재감염 | 재감염: 같은 사람에게 추가 발생한 감염")
    print("초기 감염자/외부 유입: 시뮬레이션 시작·외부에서 유입된 감염")
    print("지역 내 감염: 초기·외부 유입 이후 사람 간 전파로 생긴 감염")
    print("누적 회복/사망 사례: 재감염 전의 과거 결과도 포함")
    print(
        "설정: 회복 직후 면역 보호 "
        f"{simulation.recovered_probability:.0%}, "
        f"반감기 {simulation.recovered_immunity_half_life_days:g}일; "
        "외부 유입 시도 "
        f"{simulation.importation_rate_per_1000_per_day:g}건/1,000명/일"
    )
    print(table.to_string(col_space=8, justify="center"))

    fig, (state_axis, total_axis, mortality_axis) = plt.subplots(
        3,
        1,
        figsize=(12, 12),
        sharex=True,
    )
    result_ko[
        ["감염 가능", "잠복기", "증상 발현", "회복", "사망"]
    ].plot.area(stacked=True, ax=state_axis, alpha=0.75)
    state_axis.set_title("현재 상태별 인원 구성")
    state_axis.set_ylabel("인원")
    state_axis.legend(title="상태", loc="upper right")

    result_ko[
        [
            "현재 감염자",
            "누적 감염자",
            "감염 에피소드",
            "재감염",
            "누적 회복 사례",
            "누적 사망 사례",
        ]
    ].plot(ax=total_axis)
    total_axis.set_title("현재 감염자와 누적 감염·재감염·결과 사례")
    total_axis.set_ylabel("인원")
    total_axis.legend(title="지표", loc="best")

    result_ko["확정 사례 사망률"].plot(ax=mortality_axis)
    mortality_axis.axhline(
        y=simulation.target_cumulative_death_probability,
        color="black",
        linestyle="--",
        label="목표 누적 사망 비율 (12%)",
    )
    mortality_axis.set_title("회복·사망이 확정된 사례 중 사망 비율")
    mortality_axis.set_ylabel("사망 비율")
    mortality_axis.yaxis.set_major_formatter(PercentFormatter(1))
    mortality_axis.set_xlabel("일")
    mortality_axis.legend(loc="best")
    fig.tight_layout()
    plt.show()
    return True


if __name__ == "__main__":
    # 직접 실행할 때 사용할 기본 실험 규모와 기간.
    main(num=100_000, day=365, seed=random.randint(0, 100))
