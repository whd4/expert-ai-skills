# Method 7: First-Principles / Physics-Based Modeling

## Core idea

You know the underlying **laws** governing the system. Simulate those laws forward and the answer falls out. No historical data needed — you're not learning from the past, you're computing from physics/chemistry/biology/economics first principles.

Examples:
- Weather: Navier-Stokes + thermodynamics + radiative transfer on a grid → forecast
- Drug pharmacokinetics: rate equations for absorption/distribution/metabolism/elimination → blood concentration over time
- Rocket trajectory: Newton's laws + drag + gravity → landing zone
- Epidemic: SIR differential equations → infection curve
- Circuit: Kirchhoff's laws → voltages/currents
- Supply chain: flow equations + capacity constraints → throughput

## When to reach for it

- You have a **mechanistic** understanding (the math exists, not just correlations)
- You need to **extrapolate** beyond observed data (what happens at temperatures we haven't measured?)
- Historical data is scarce or unreliable for the regime you care about
- You need **explainable** predictions (every variable has physical meaning)

## When NOT to use it

- You don't know the governing equations → use ML or Bayesian
- The system has too many unknowns (complex adaptive social systems) → use simulation or crowd
- You just need a short-horizon forecast and have data → use statistical forecasting

## The main toolkits

### 1. Ordinary differential equations (ODE)
`dy/dt = f(y, t)` — variables evolve over time based on a rate law.
Python: `scipy.integrate.solve_ivp`, `odeint`.
Examples: population dynamics, chemical kinetics, pharmacokinetics.

### 2. Partial differential equations (PDE)
Variables change over time AND space. Navier-Stokes, heat equation, wave equation.
Python: `fenics`, `firedrake`, `fipy`. Heavy-lift: specialized CFD codes (OpenFOAM).

### 3. Discrete event simulation
System has events at specific times (arrivals, completions, failures).
Python: `SimPy`.
Examples: hospital operations, factory throughput, server queues.

### 4. Agent-based modeling
Many agents with rules, observe emergent behavior.
Python: `mesa`.
Examples: traffic flow (Schelling), epidemics, market microstructure.

### 5. System dynamics
Stock-and-flow diagrams with feedback loops.
Tools: `pysd`, Vensim, Stella.
Examples: Limits to Growth, organizational dynamics, climate.

### 6. Finite element / finite volume
Discretize continuous systems into computational grids.
Tools: ANSYS, Abaqus (commercial); FEniCS (open).
Examples: structural analysis, heat transfer, fluid flow.

## Decision tree

```
Do you know the governing equations?
├── NO → switch to ML or Bayesian
└── YES → what kind?
    ├── Time-only, continuous → ODE (scipy.integrate)
    ├── Time + space, continuous → PDE (fenics or specialized)
    ├── Discrete events → SimPy
    ├── Many interacting entities → agent-based (mesa)
    ├── Stocks and flows with feedback → system dynamics (pysd)
    └── Mechanical structure → finite element (FEniCS or ANSYS)
```

## Integration with this toolkit

First-principles models are **deterministic** given inputs. To add uncertainty:

1. **Monte Carlo wrapper** — sample uncertain inputs (material properties, rate constants, initial conditions), run the simulation N times, get outcome distribution. This is the most common combination.

2. **Bayesian calibration** — use observed data to update priors on the model's parameters (e.g., reaction rate constants).

3. **Ensemble forecasting** — run the model with small perturbations to initial conditions (weather uses this).

4. **Sensitivity analysis** — which input parameters move the output most? This is essentially a tornado chart, built into the monte-carlo-predictor skill.

## Classic patterns

### Pattern 1: Point prediction from a model
```
Given initial state + parameters → ODE solve → outcome
```

### Pattern 2: Uncertainty quantification
```
Sample parameters (prior distributions) → Monte Carlo over ODE solves → distribution of outcomes
```

### Pattern 3: Parameter estimation (inverse problem)
```
Observed data → Bayesian / maximum likelihood → posterior on parameters → forward simulate
```

## Honest limits

- Models are wrong; some are useful (Box). All models are approximations.
- **Structural misspecification** — if the governing equations don't match reality, no amount of parameter tuning fixes it.
- **Computational cost** — full CFD simulations can take hours; ODEs are fast but still slower than statistical methods.
- **Calibration traps** — fitting a model to historical data doesn't guarantee predictive accuracy.

## External reading

- Strogatz, "Nonlinear Dynamics and Chaos" — for ODE intuition
- Zwillinger, "Handbook of Differential Equations" — reference
- `scipy.integrate` docs: https://docs.scipy.org/doc/scipy/reference/integrate.html
- "Modeling Complex Systems" (Boccara) — cross-method overview
