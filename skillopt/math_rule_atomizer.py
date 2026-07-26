"""Math-specific atomic rules for cross-task architecture validation.

Same architecture as rule_atomizer.py (Core + Dynamic, trigger/text),
but rules written for math multiple-choice reasoning — NOT SearchQA.
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class AtomicRule:
    id: str; text: str; trigger: str; keywords: list[str]
    is_core: bool; tags: list[str]

CORE_RULES = [
    AtomicRule("M01", "Read the full question and ALL answer choices before solving.", "read all choices before solving", ["read","all","choices"], True, ["strategy"]),
    AtomicRule("M02", "Identify what type of problem this is: algebra, geometry, probability, calculus, number theory, or logic.", "identify problem type algebra geometry probability calculus", ["algebra","geometry","probability","calculus","logic"], True, ["strategy"]),
    AtomicRule("M03", "Solve step by step. Show intermediate results. At the end, output ONLY the letter of the correct choice.", "solve step by step output letter only", ["solve","step","letter"], True, ["strategy","output"]),
    AtomicRule("M04", "After solving, verify your answer by plugging it back or checking against constraints.", "verify answer check constraints plug back", ["verify","check"], True, ["strategy"]),
    AtomicRule("M05", "Pay attention to units, signs, and domain restrictions (e.g., x>0, denominator≠0).", "units signs domain restrictions denominator", ["units","sign","domain"], True, ["strategy"]),
]

DYNAMIC_RULES = [
    AtomicRule("M06", "For algebra equations: isolate the variable step by step. Check each operation is reversible.", "algebra equation isolate variable solve for x", ["equation","solve","variable","x"], False, ["algebra"]),
    AtomicRule("M07", "For systems of equations: use substitution or elimination. Solve for one variable first.", "system of equations substitution elimination two variables", ["system","substitution","elimination"], False, ["algebra"]),
    AtomicRule("M08", "For quadratic equations ax²+bx+c=0: use factoring, completing the square, or quadratic formula x=(-b±√(b²-4ac))/2a.", "quadratic factoring completing square formula discriminant", ["quadratic","factoring","discriminant"], False, ["algebra"]),
    AtomicRule("M09", "For inequalities: remember to flip the sign when multiplying or dividing by a negative number.", "inequality flip sign negative multiply divide", ["inequality","flip","negative"], False, ["algebra"]),
    AtomicRule("M10", "For geometry problems: draw a diagram. Label known values. Use Pythagoras, similar triangles, circle theorems.", "geometry triangle circle angle area Pythagoras similar", ["geometry","triangle","circle","angle"], False, ["geometry"]),
    AtomicRule("M11", "For coordinate geometry: use distance formula, midpoint, slope. y=mx+b for lines.", "coordinate geometry distance midpoint slope line equation", ["coordinate","distance","slope","line"], False, ["geometry"]),
    AtomicRule("M12", "For area/volume: recall formulas. Rectangle=lw, triangle=½bh, circle=πr², sphere=4/3πr³.", "area volume surface rectangle triangle circle sphere formula", ["area","volume","formula"], False, ["geometry"]),
    AtomicRule("M13", "For probability: P(A)=favorable/total. For independent events multiply. For 'at least one' use complement.", "probability favorable total independent complement at least one", ["probability","independent","complement"], False, ["probability"]),
    AtomicRule("M14", "For combinatorics: use permutations (order matters) or combinations (order doesn't). nPr=n!/(n-r)!, nCr=n!/(r!(n-r)!).", "permutation combination factorial nPr nCr order matters", ["permutation","combination","factorial"], False, ["probability"]),
    AtomicRule("M15", "For expected value: sum of (value × probability of that value).", "expected value mean sum product probability", ["expected","value","mean"], False, ["probability"]),
    AtomicRule("M16", "For calculus derivatives: power rule d/dx(xⁿ)=nxⁿ⁻¹, product rule, chain rule, quotient rule.", "derivative power rule product chain quotient differentiation", ["derivative","differentiation","chain","rule"], False, ["calculus"]),
    AtomicRule("M17", "For calculus integrals: ∫xⁿdx=xⁿ⁺¹/(n+1)+C. For definite integrals evaluate F(b)-F(a).", "integral antiderivative definite indefinite fundamental theorem", ["integral","antiderivative","definite"], False, ["calculus"]),
    AtomicRule("M18", "For limits: try direct substitution first. If 0/0, try factoring, L'Hôpital's rule, or algebraic manipulation.", "limit direct substitution L'Hopital factoring indeterminate form", ["limit","substitution","indeterminate"], False, ["calculus"]),
    AtomicRule("M19", "For number theory: use divisibility rules, prime factorization, GCD/LCM, modular arithmetic.", "number theory prime factor divisibility GCD LCM modular", ["prime","factor","gcd","modular"], False, ["number_theory"]),
    AtomicRule("M20", "For sequences/series: identify pattern. Arithmetic: aₙ=a₁+(n-1)d. Geometric: aₙ=a₁rⁿ⁻¹. Sum formulas.", "sequence series arithmetic geometric pattern sum formula", ["sequence","series","arithmetic","geometric"], False, ["algebra"]),
    AtomicRule("M21", "For logarithms: logₐ(xy)=logₐx+logₐy, logₐ(x/y)=logₐx-logₐy, logₐ(xⁿ)=n·logₐx.", "logarithm log product quotient power property base", ["log","logarithm","base","exponent"], False, ["algebra"]),
    AtomicRule("M22", "For trigonometry: SOHCAHTOA, sin²+cos²=1, law of sines a/sinA=b/sinB, law of cosines c²=a²+b²-2ab·cosC.", "trigonometry sin cos tan SOHCAHTOA law of sines cosines", ["sin","cos","tan","trig","triangle"], False, ["geometry"]),
    AtomicRule("M23", "For functions: find domain (exclude division by zero, negative under even root). Find range. Check if 1-to-1.", "function domain range one-to-one inverse composition", ["function","domain","range","inverse"], False, ["algebra"]),
]

ALL_RULES = CORE_RULES + DYNAMIC_RULES
CORE_TEXTS = [r.text for r in CORE_RULES]
DYNAMIC_TRIGGERS = [r.trigger for r in DYNAMIC_RULES]
DYNAMIC_TEXTS = [r.text for r in DYNAMIC_RULES]
