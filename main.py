"""시뮬레이션을 실행하고 일별 감염자 수를 그래프로 표시한다."""

import matplotlib.pyplot as plt

from Simulation import Simulation


def main(num=100, day=5, seed: int = 0):
    # 실험 인원과 난수 시드를 전달해 초기 상태를 만든다.
    simulation = Simulation()
    simulation.setup(num, random_seed=seed)

    # 지정한 날짜 수만큼 진행한 뒤, 일별 감염자 수를 그린다.
    simulation.run(day)
    plt.plot(simulation.result)
    plt.ylabel("infected people")
    plt.xlabel("day")
    plt.show()
    return True


if __name__ == "__main__":
    # 직접 실행할 때 사용할 기본 실험 규모와 기간.
    main(num=10_000, day=100, seed=42)
