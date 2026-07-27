"""NSGA-II (Non-dominated Sorting Genetic Algorithm II) for binary rule selection.

Pure numpy implementation — zero external dependencies beyond numpy.
Operates on raw arrays; no file I/O, no skillopt imports.

Reference: Deb et al. (2002) "A Fast and Elitist Multiobjective Genetic Algorithm: NSGA-II"
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# ── Configuration ────────────────────────────────────────────────────────────


@dataclass
class NSGA2Config:
    """NSGA-II hyperparameters.

    pop_size:     Population size (must be even).
    generations:  Number of generations to evolve.
    crossover_p:  Probability of uniform crossover per gene pair.
    mutation_p:   Per-gene bit-flip probability.
    tourn_size:   Binary tournament selection size.
    """
    pop_size: int = 50
    generations: int = 30
    crossover_p: float = 0.9
    mutation_p: float = 0.10
    tourn_size: int = 2


# ── Public API ───────────────────────────────────────────────────────────────


def optimize(
    fitness_func,
    n_vars: int,
    budget: int,
    token_costs: np.ndarray,
    config: NSGA2Config | None = None,
    rng: np.random.RandomState | None = None,
    callback=None,
):
    """Run NSGA-II to find Pareto-optimal rule subsets.

    Parameters
    ----------
    fitness_func : callable
        ``fitness_func(population) -> objectives`` where
        ``population`` has shape ``(pop_size, n_vars)`` (binary) and
        ``objectives`` has shape ``(pop_size, n_objectives)`` (all minimized).
    n_vars : int
        Number of dynamic rules (chromosome length).
    budget : int
        Token budget constraint.
    token_costs : np.ndarray
        Shape ``(n_vars,)`` — token length per rule for constraint checks.
    config : NSGA2Config | None
        Algorithm hyperparameters (uses defaults if None).
    rng : np.random.RandomState | None
        Random state for reproducibility.
    callback : callable | None
        Optional ``callback(generation, population, objectives)`` per generation.

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        ``(pareto_chromosomes, pareto_objectives)`` — the rank-0 front.
    """
    cfg = config or NSGA2Config()
    rng = rng or np.random.RandomState()

    if n_vars == 0:
        return np.empty((0, 0)), np.empty((0, 0))

    # ── Initialise ───────────────────────────────────────────────────────
    pop = _init_population(cfg.pop_size, n_vars, rng)
    obj = fitness_func(pop)
    violations = _constraint_violations(pop, budget, token_costs)
    for gen_idx in range(cfg.generations):
        # ── Rank & distance ──────────────────────────────────────────────
        fronts = _non_dominated_sort(obj, violations)
        crowd = _crowding_distance(obj, fronts)

        # ── Create offspring ─────────────────────────────────────────────
        offspring = _create_offspring(pop, obj, fronts, crowd, violations,
                                       budget, token_costs, cfg, rng)
        off_obj = fitness_func(offspring)
        off_violations = _constraint_violations(offspring, budget, token_costs)

        # ── Elitist environmental selection ──────────────────────────────
        merged = np.vstack([pop, offspring])
        merged_obj = np.vstack([obj, off_obj])
        merged_viol = np.concatenate([violations, off_violations])

        merged_fronts = _non_dominated_sort(merged_obj, merged_viol)
        merged_crowd = _crowding_distance(merged_obj, merged_fronts)

        surv = _select_survivors(merged, merged_obj, merged_fronts,
                                  merged_crowd, merged_viol, cfg.pop_size)

        pop = merged[surv]
        obj = merged_obj[surv]
        violations = merged_viol[surv]

        if callback is not None:
            callback(gen_idx, pop, obj)

    # ── Return rank-0 (Pareto front) ────────────────────────────────────
    final_fronts = _non_dominated_sort(obj, violations)
    pareto_idx = np.array(final_fronts[0], dtype=int)
    return pop[pareto_idx], obj[pareto_idx]


# ── Initialisation ───────────────────────────────────────────────────────────


def _init_population(pop_size: int, n_vars: int, rng: np.random.RandomState) -> np.ndarray:
    """Random binary population, biased toward sparse selections.

    Each gene is 1 with probability min(0.25, 5/n_vars) so initial solutions
    select ~5 rules on average, avoiding all-zero or all-one chromosomes.
    """
    p = min(0.25, 5.0 / max(n_vars, 1))
    return (rng.rand(pop_size, n_vars) < p).astype(np.float64)


# ── Non-dominated sorting ────────────────────────────────────────────────────


def _non_dominated_sort(
    objectives: np.ndarray,
    violations: np.ndarray,
) -> list[list[int]]:
    """Fast non-dominated sort (Deb et al. 2002).

    Returns list of fronts; each front is a list of population indices.
    Feasible solutions always dominate infeasible ones.
    """
    n = len(objectives)
    dominated_by = np.zeros(n, dtype=int)        # n_p: solutions that dominate p
    dominates = [set() for _ in range(n)]         # S_p: solutions that p dominates
    fronts: list[list[int]] = [[]]

    for p in range(n):
        for q in range(n):
            if p == q:
                continue
            if _dominates(p, q, objectives, violations):
                dominates[p].add(q)
            elif _dominates(q, p, objectives, violations):
                dominated_by[p] += 1
        if dominated_by[p] == 0:
            fronts[0].append(p)

    i = 0
    while fronts[i]:
        next_front: list[int] = []
        for p in fronts[i]:
            for q in dominates[p]:
                dominated_by[q] -= 1
                if dominated_by[q] == 0:
                    next_front.append(q)
        i += 1
        if next_front:
            fronts.append(next_front)
        else:
            break

    return fronts


def _dominates(
    p: int, q: int,
    objectives: np.ndarray,
    violations: np.ndarray,
) -> bool:
    """Return True if solution p dominates solution q.

    Feasibility-first: feasible dominates infeasible.
    Among infeasible: lower violation dominates.
    Among feasible: standard Pareto dominance (strictly better in >=1 objective,
    not worse in any).
    """
    p_feas = violations[p] <= 0.0
    q_feas = violations[q] <= 0.0
    if p_feas and not q_feas:
        return True
    if not p_feas and q_feas:
        return False
    if not p_feas and not q_feas:
        return violations[p] < violations[q]

    # Both feasible: Pareto dominance (all objectives minimised)
    obj_p = objectives[p]
    obj_q = objectives[q]
    better = False
    for m in range(len(obj_p)):
        if obj_p[m] > obj_q[m]:
            return False
        if obj_p[m] < obj_q[m]:
            better = True
    return better


# ── Crowding distance ────────────────────────────────────────────────────────


def _crowding_distance(
    objectives: np.ndarray,
    fronts: list[list[int]],
) -> np.ndarray:
    """Compute crowding distance for each solution.

    Boundary solutions in each front get infinite distance.
    Interior solutions get sum of normalised gap per objective.
    """
    n_obj = objectives.shape[1]
    dist = np.zeros(len(objectives))

    for front in fronts:
        if len(front) <= 2:
            dist[front] = np.inf
            continue

        front_arr = np.array(front)
        for m in range(n_obj):
            vals = objectives[front_arr, m]
            order = np.argsort(vals)
            sorted_front = front_arr[order]
            sorted_vals = vals[order]

            obj_range = sorted_vals[-1] - sorted_vals[0]
            if obj_range < 1e-12:
                continue  # all equal — no distance contribution

            dist[sorted_front[0]] = np.inf
            dist[sorted_front[-1]] = np.inf
            for i in range(1, len(sorted_front) - 1):
                dist[sorted_front[i]] += (
                    (sorted_vals[i + 1] - sorted_vals[i - 1]) / obj_range
                )

    return dist


# ── Selection ────────────────────────────────────────────────────────────────


def _select_survivors(
    population: np.ndarray,
    objectives: np.ndarray,
    fronts: list[list[int]],
    crowding: np.ndarray,
    violations: np.ndarray,
    n_select: int,
) -> np.ndarray:
    """Select n_select survivors from merged population.

    Fill fronts in order.  If a front doesn't fit entirely, take the
    individuals with highest crowding distance from that front.
    """
    selected: list[int] = []
    for front in fronts:
        if len(selected) + len(front) <= n_select:
            selected.extend(front)
        else:
            # Need to split this front — take best by crowding distance
            remaining = n_select - len(selected)
            front_indices = np.array(list(front))
            crowd_order = np.argsort(-crowding[front_indices])
            selected.extend(front_indices[crowd_order[:remaining]].tolist())
            break
    return np.array(selected, dtype=int)


# ── Genetic operators ────────────────────────────────────────────────────────


def _tournament_select(
    population: np.ndarray,
    objectives: np.ndarray,
    fronts: list[list[int]],
    crowding: np.ndarray,
    violations: np.ndarray,
    rng: np.random.RandomState,
) -> int:
    """Binary tournament: pick 2 random individuals, return the better one."""
    idx = rng.choice(len(population), size=2, replace=False)

    # Compare by front rank first, then crowding distance, then feasibility
    rank = np.full(len(population), -1, dtype=int)
    for fi, front in enumerate(fronts):
        for pi in front:
            rank[pi] = fi

    r0, r1 = rank[idx[0]], rank[idx[1]]
    if r0 != r1:
        return idx[0] if r0 < r1 else idx[1]

    c0, c1 = crowding[idx[0]], crowding[idx[1]]
    if c0 != c1:
        return idx[0] if c0 > c1 else idx[1]

    # Tie-break: feasibility
    v0, v1 = violations[idx[0]], violations[idx[1]]
    if v0 <= 0 and v1 > 0:
        return idx[0]
    if v1 <= 0 and v0 > 0:
        return idx[1]
    return idx[0] if v0 <= v1 else idx[1]


def _create_offspring(
    population: np.ndarray,
    objectives: np.ndarray,
    fronts: list[list[int]],
    crowding: np.ndarray,
    violations: np.ndarray,
    budget: int,
    token_costs: np.ndarray,
    config: NSGA2Config,
    rng: np.random.RandomState,
) -> np.ndarray:
    """Generate offspring via tournament selection, crossover, mutation."""
    pop_size, n_vars = population.shape
    offspring = np.empty((pop_size, n_vars))

    for i in range(0, pop_size, 2):
        p1 = _tournament_select(population, objectives, fronts,
                                 crowding, violations, rng)
        p2 = _tournament_select(population, objectives, fronts,
                                 crowding, violations, rng)
        c1, c2 = _uniform_crossover(population[p1], population[p2],
                                     config.crossover_p, rng)
        c1 = _bit_flip_mutation(c1, config.mutation_p, rng)
        c2 = _bit_flip_mutation(c2, config.mutation_p, rng)

        # Repair: if offspring exceeds budget, drop lowest-scoring rules
        if np.dot(c1, token_costs) > budget:
            c1 = _repair_budget(c1, token_costs, budget, rng)
        if np.dot(c2, token_costs) > budget:
            c2 = _repair_budget(c2, token_costs, budget, rng)

        offspring[i] = c1
        if i + 1 < pop_size:
            offspring[i + 1] = c2

    return offspring


def _uniform_crossover(
    parent1: np.ndarray,
    parent2: np.ndarray,
    prob: float,
    rng: np.random.RandomState,
) -> tuple[np.ndarray, np.ndarray]:
    """Uniform crossover: each gene independently inherited from p1 or p2."""
    mask = rng.rand(len(parent1)) < 0.5
    c1 = np.where(mask, parent1, parent2)
    c2 = np.where(mask, parent2, parent1)
    if rng.rand() < prob:
        return c1, c2
    return parent1.copy(), parent2.copy()


def _bit_flip_mutation(
    chrom: np.ndarray,
    prob: float,
    rng: np.random.RandomState,
) -> np.ndarray:
    """Independent per-gene bit-flip mutation."""
    flip = rng.rand(len(chrom)) < prob
    mut = chrom.copy()
    mut[flip] = 1.0 - mut[flip]
    return mut


def _repair_budget(
    chrom: np.ndarray,
    token_costs: np.ndarray,
    budget: int,
    rng: np.random.RandomState,
) -> np.ndarray:
    """Drop selected rules (random order) until budget is satisfied."""
    selected = np.where(chrom > 0.5)[0]
    if len(selected) == 0:
        return chrom
    # Drop in random order
    rng.shuffle(selected)
    repaired = chrom.copy()
    current_cost = np.dot(repaired, token_costs)
    for idx in selected:
        if current_cost <= budget:
            break
        repaired[idx] = 0.0
        current_cost -= token_costs[idx]
    return repaired


# ── Constraint utilities ─────────────────────────────────────────────────────


def _constraint_violations(
    population: np.ndarray,
    budget: int,
    token_costs: np.ndarray,
) -> np.ndarray:
    """Compute token budget violations for the population.

    violation = max(0, sum(token_costs) - budget) per individual.
    """
    costs = population @ token_costs  # shape (pop_size,)
    return np.maximum(0.0, costs - budget)
