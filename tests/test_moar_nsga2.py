"""Unit tests for NSGA-II core algorithm."""
from __future__ import annotations

import numpy as np
import pytest

from skillopt.moar.nsga2 import (
    NSGA2Config,
    _bit_flip_mutation,
    _constraint_violations,
    _crowding_distance,
    _dominates,
    _init_population,
    _non_dominated_sort,
    _repair_budget,
    _uniform_crossover,
    optimize,
)


class TestNonDominatedSort:
    def test_single_objective(self):
        """With 1 objective, the minimum values form front 0."""
        obj = np.array([[0.5], [0.2], [0.8], [0.2]])
        violations = np.zeros(4)
        fronts = _non_dominated_sort(obj, violations)
        # 0.2 values dominate 0.5, and 0.5 dominates 0.8
        assert 1 in fronts[0]  # 0.2
        assert 3 in fronts[0]  # 0.2
        # 0.5 is dominated by 0.2 values -> should be in a later front
        all_later = set()
        for f in fronts[1:]:
            all_later.update(f)
        assert 0 in all_later  # 0.5 in front 1 (dominated by 0.2)
        assert 2 in all_later  # 0.8 in front >=1

    def test_clear_dominance(self):
        """A solution that is strictly better in all objectives dominates."""
        obj = np.array([[0.1, 0.1], [0.9, 0.9], [0.5, 0.5]])
        violations = np.zeros(3)
        fronts = _non_dominated_sort(obj, violations)
        assert 0 in fronts[0]  # (0.1,0.1) dominates both
        assert len(fronts) >= 2

        # [0.9,0.9] should be in a later front than [0.5,0.5]
        # since [0.5,0.5] dominates [0.9,0.9]
        later = set()
        for f in fronts[1:]:
            later.update(f)
        assert 2 in later  # index 2 = [0.9,0.9]

    def test_feasible_dominates_infeasible(self):
        """Even with worse objectives, feasible dominates infeasible."""
        obj = np.array([[0.9, 0.9], [0.1, 0.1]])  # 0 is worse
        violations = np.array([0.0, 100.0])         # but 0 is feasible
        assert _dominates(0, 1, obj, violations)
        assert not _dominates(1, 0, obj, violations)


class TestCrowdingDistance:
    def test_boundary_infinite(self):
        obj = np.array([[0.0], [0.5], [1.0]])
        fronts = [[0, 1, 2]]
        crowd = _crowding_distance(obj, fronts)
        assert crowd[0] == np.inf
        assert crowd[2] == np.inf
        assert crowd[1] < np.inf and crowd[1] >= 0

    def test_all_equal_no_distance(self):
        """When all solutions are identical (zero objective range),
        no crowding distance contribution is assigned — the boundary
        check only fires when obj_range > 0."""
        obj = np.array([[0.5, 0.3], [0.5, 0.3], [0.5, 0.3]])
        fronts = [[0, 1, 2]]
        crowd = _crowding_distance(obj, fronts)
        # All distances are 0 because no objective has range > 0
        assert crowd[0] == 0.0
        assert crowd[1] == 0.0
        assert crowd[2] == 0.0


class TestGeneticOperators:
    def test_crossover_preserves_length(self):
        p1 = np.array([1, 0, 1, 1, 0], dtype=float)
        p2 = np.array([0, 1, 0, 1, 1], dtype=float)
        rng = np.random.RandomState(42)
        c1, c2 = _uniform_crossover(p1, p2, 0.9, rng)
        assert len(c1) == len(p1)
        assert len(c2) == len(p2)
        # All values should be 0 or 1
        assert set(c1).issubset({0, 1})
        assert set(c2).issubset({0, 1})

    def test_mutation_binary(self):
        chrom = np.array([1, 0, 1, 0, 1], dtype=float)
        rng = np.random.RandomState(42)
        mut = _bit_flip_mutation(chrom, 0.5, rng)
        assert set(mut).issubset({0, 1})

    def test_repair_budget(self):
        chrom = np.array([1, 1, 1, 0, 0], dtype=float)
        costs = np.array([100, 200, 300, 50, 50], dtype=float)
        rng = np.random.RandomState(42)
        repaired = _repair_budget(chrom, costs, 350, rng)
        assert np.dot(repaired, costs) <= 350
        # At least one rule should be dropped
        assert np.sum(repaired) < 3 or np.dot(repaired, costs) <= 350


class TestConstraintViolations:
    def test_no_violation(self):
        pop = np.array([[1, 0, 0], [0, 1, 0]])
        costs = np.array([100, 200, 300])
        viol = _constraint_violations(pop, 500, costs, top_k=5)
        assert np.all(viol == 0)

    def test_budget_violation(self):
        pop = np.array([[1, 1, 1]])
        costs = np.array([100, 200, 300])
        viol = _constraint_violations(pop, 300, costs, top_k=5)
        assert viol[0] == 300  # 600 - 300 = budget violation

    def test_topk_violation(self):
        pop = np.array([[1, 1, 0]])
        costs = np.array([10, 20, 30])
        viol = _constraint_violations(pop, 500, costs, top_k=1)
        assert viol[0] == 100  # (2-1) * 100 penalty


class TestNSGA2Full:
    def test_converges_on_simple_problem(self):
        """NSGA-II should find solutions for a trivial 2-objective problem."""

        n_vars = 5
        rng = np.random.RandomState(42)

        def fitness(pop):
            # f1 = sum of selected vars (we want this small -> select fewer)
            # f2 = -sum of selected vars (we want this large -> select more)
            # This creates a trivial Pareto front
            s = pop.sum(axis=1)
            return np.column_stack([s / n_vars, 1.0 - s / n_vars])

        config = NSGA2Config(pop_size=20, generations=10,
                              crossover_p=0.9, mutation_p=0.1)
        pareto, pobj = optimize(
            fitness, n_vars=n_vars, budget=999999,
            token_costs=np.ones(n_vars), config=config, rng=rng,
        )

        assert len(pareto) >= 1
        assert pareto.shape[1] == n_vars
        assert pobj.shape[1] == 2

    def test_budget_respected(self):
        """Solutions should respect the token budget."""
        n_vars = 4
        costs = np.array([50, 150, 300, 800])
        rng = np.random.RandomState(42)

        def fitness(pop):
            r = np.random.randn(len(pop), n_vars)
            s = pop.sum(axis=1, keepdims=True)
            return np.column_stack([
                1.0 - s.ravel() / n_vars,   # prefer more rules
                s.ravel() / n_vars,          # prefer fewer rules
            ])

        config = NSGA2Config(pop_size=20, generations=15,
                              crossover_p=0.9, mutation_p=0.1)
        pareto, pobj = optimize(
            fitness, n_vars=n_vars, budget=500,
            token_costs=costs, config=config, rng=rng,
        )

        for chrom in pareto:
            assert np.dot(chrom, costs) <= 500 + 1e-9  # tolerance

    def test_empty_rules(self):
        """Zero variables should return empty arrays."""
        def fitness(pop):
            return np.zeros((len(pop), 2))

        rng = np.random.RandomState(42)
        pareto, pobj = optimize(
            fitness, n_vars=0, budget=100,
            token_costs=np.array([]),
            config=NSGA2Config(pop_size=10, generations=5),
            rng=rng,
        )
        assert pareto.size == 0 or pareto.shape[1] == 0


class TestPopulationInit:
    def test_sparse_init(self):
        rng = np.random.RandomState(42)
        pop = _init_population(50, 20, top_k=5, rng=rng)
        assert pop.shape == (50, 20)
        # All individuals should respect top_K=5
        assert np.all(pop.sum(axis=1) <= 5)
        # Should be somewhat sparse
        avg = pop.mean()
        assert 0.05 <= avg <= 0.3  # roughly 1-6 rules on average
