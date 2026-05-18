import math

def fixed_decay_score(base_points: int, decay_rate: int, solves_count: int, min_points: int = 0):

    score = max(base_points - decay_rate * solves_count, min_points)
    return score

def find_decay_rate_for_exponent(base_points: int, min_points: int, teams_count: int):
    points_range = base_points - min_points
    last_solve_index = teams_count - 1

    if points_range <= 0 or last_solve_index <= 0:
        return 0.0

    target_points_above_min = min(1.0, points_range)
    exponent_decay_rate = -math.log(target_points_above_min / points_range) / last_solve_index
    return exponent_decay_rate

def exponential_decay_score(base_points: int, solves_count: int, teams_count: int, min_points: int = 0):

    decay_rate = find_decay_rate_for_exponent(base_points, min_points, teams_count)
    score = min_points + (base_points - min_points) * math.exp(-decay_rate * solves_count)
    return score, decay_rate


if __name__ == "__main__":
    base_points = 500
    min_points = 400
    teams_count = 30


    print("\nExponential Decay:")
    for solves in range(teams_count):
        score, decay_rate = exponential_decay_score(base_points, solves, teams_count, min_points)

        print(f"Solves: {solves}, Score: {score}")
        print(f"Decay Rate: {decay_rate}")
