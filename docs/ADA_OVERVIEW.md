# ADA Overview

## What ADA Is

ADA, short for **AI Design Assistant**, is a local Python application for **airfoil design and analysis**. It combines:

- A browser-based interface
- A natural-language command workflow
- Airfoil geometry generation and editing
- Aerodynamic analysis through external solvers
- Plotting and session-based result management

In its current state, ADA is best described as an **AI-assisted airfoil analysis workbench** rather than a general aircraft design platform.

## What ADA Does Today

ADA is organized around a few core capabilities that are already wired into the application.

### 1. Natural-language design interaction

Users interact with ADA by typing requests such as:

- `generate a naca2412 airfoil`
- `create an xfoil analysis case`
- `set alpha to 4.0`
- `run case`
- `plot the boundary layer`

The UI layer translates those requests into tool calls and updates the current design session.

### 2. Airfoil generation and geometry management

ADA can create and manage multiple airfoils during a session.

Supported geometry workflows in the current codebase include:

- Generating **NACA 4-digit airfoils**
- Loading named airfoils from the repository's airfoil databases
- Representing airfoils with **Kulfan/CST-style parameterization**
- Editing upper and lower surface coefficients directly
- Copying geometries and switching the active airfoil
- Displaying the active airfoil in the graphics window

This makes ADA useful for both starting from standard airfoils and iterating on parameterized shapes.

### 3. XFOIL analysis case setup and execution

The primary integrated analysis tool is **XFOIL**.

ADA currently supports:

- Creating XFOIL analysis cases
- Switching between multiple analysis cases
- Editing case inputs such as:
  - angle of attack
  - target lift coefficient
  - Reynolds number
  - Mach number
  - transition settings
  - panel count
  - N-crit
- Running single-point analyses
- Running sweeps by passing ranges or value lists
- Locking geometry/analysis objects after runs so results remain traceable
- Saving analysis case data in a serializable format

Internally, ADA writes temporary execution files, calls the `xfoil` executable, and collects aerodynamic outputs like:

- `Cl`
- `Cd`
- `Cm`
- transition locations
- pressure coefficient data
- boundary-layer data

### 4. Plotting and result exploration

ADA can generate plots from completed XFOIL runs and show them in the UI.

Current plotting features include:

- Force plots
- Boundary-layer parameter plots
- Polar plots for sweep results
- Standard XFOIL-style summary plots

The UI also supports selecting, deselecting, and clearing active datasets so users can compare results across runs.

## What a User Gains From ADA

ADA helps users move from asking broad design questions to getting concrete aerodynamic evidence. Instead of manually switching between geometry files, solver inputs, and plotting scripts, the user can explore airfoil behavior in one interactive workflow.

For a user, ADA is valuable because it supports:

- faster iteration on airfoil ideas
- easier comparison between candidate geometries
- clearer understanding of how flow conditions affect performance
- lower friction for students or engineers learning aerodynamic trends
- more direct access to solver outputs without manually building every post-processing step

In practice, ADA helps turn questions like these into something testable:

- How does changing camber or thickness affect lift and drag?
- What happens to performance as angle of attack changes?
- How sensitive is this airfoil to Reynolds number?
- Where does transition occur on the upper and lower surfaces?
- How does the boundary layer evolve around the section?
- Which candidate airfoil is better for a given operating condition?

## What Users Can Study and Learn

ADA is especially useful for studying **cause and effect** in 2D aerodynamic design.

With the current workflow, a user can learn about:

- the relationship between airfoil geometry and aerodynamic performance
- how lift, drag, and pitching moment change across operating conditions
- how boundary-layer properties vary along the airfoil surface
- how airfoil performance changes across sweeps in angle of attack or target lift
- how transition location moves with Reynolds number, Mach number, and geometry changes
- how different airfoils compare under the same analysis setup

This is important because it gives the user more than just a final number. It helps them understand **why** an airfoil behaves the way it does and which design changes are likely to improve or degrade performance.

## What Data ADA Can Provide

From the currently integrated XFOIL workflow, ADA can provide or derive several useful classes of data.

### Scalar performance outputs

These are the high-level aerodynamic metrics users typically look at first:

- lift coefficient (`Cl`)
- drag coefficient (`Cd`)
- pitching moment coefficient (`Cm`)
- angle of attack or target lift solution values
- upper and lower transition locations

These values matter because they help answer first-order design questions about efficiency, load generation, trim behavior, and operating range.

### Surface and flowfield-related data

ADA can also expose more detailed data used to interpret *why* a result occurred:

- pressure coefficient (`Cp`) distributions
- boundary-layer data along the surface
- shape parameter and related boundary-layer quantities
- momentum-thickness and displacement-thickness style information from the boundary-layer output

These are important because they let the user inspect whether an airfoil is producing a result through healthy flow behavior or through conditions that may be close to separation, excessive losses, or poor robustness.

### Sweep and comparison data

When users run parameter sweeps, ADA can generate result sets suitable for trend analysis:

- lift-drag trends across angle-of-attack sweeps
- polar data for comparing multiple configurations
- multi-case comparisons across Reynolds number or other inputs
- side-by-side dataset selection for plotting and review

This matters because most design decisions are not made from a single operating point. Sweeps help users understand performance envelopes and tradeoffs.

## Why This Matters

ADA is useful not only because it automates analysis, but because it shortens the path from **idea** to **evidence**.

That matters for:

- students learning aerodynamics through immediate feedback
- researchers exploring design sensitivity and trends
- engineers screening section concepts before deeper analysis
- anyone who wants a more conversational interface to aerodynamic study

The combination of natural-language control, geometry editing, automated solver execution, and built-in plotting makes ADA helpful as both a **learning tool** and a **rapid analysis environment**.

### 5. Local browser UI and session management

ADA runs as a local HTTP server and opens a browser-based interface from the user's home directory via `.ada/index.html`.

The UI maintains session state for:

- queries and responses
- geometry objects
- analysis cases
- generated datasets
- plot/image outputs
- graphics window content

This gives ADA a lightweight interactive workflow without requiring a separate hosted backend.

### 6. LLM-backed assistant behavior

ADA includes an LLM runtime layer that can use either:

- OpenAI models
- A local OpenAI-compatible endpoint

The runtime auto-detects whether to use a local provider or OpenAI unless the environment forces one explicitly.

This allows ADA to operate as an AI front end for the engineering workflow while keeping the analysis itself local.

## Important Current Limitations

The repository also contains signs of broader ambition, but not all of it is fully active in the current product path.

- **XFOIL is the only analysis tool currently registered in the active UI tool list.**
- **MSES-related code exists in the repository**, but it is not currently exposed as a selectable analysis tool in the main UI flow.
- The project is focused on **2D airfoil workflows**, not full aircraft sizing or multidisciplinary aircraft design.
- An `optimization` package exists, but there is not yet a clearly integrated end-to-end optimization workflow in the current UI.
- ADA depends on external local tooling such as `xfoil`, and parts of the workflow also expect `timelimit` to be available.

## What ADA Is Capable Of in Practice

For a user today, ADA is capable of the following practical workflow:

1. Create or load an airfoil
2. Adjust its shape using parameterized geometry controls
3. Create an XFOIL case
4. Set aerodynamic conditions or sweeps
5. Run the analysis
6. Review forces, boundary-layer behavior, and polar results
7. Compare multiple geometries, cases, and datasets in one session

That makes ADA a strong foundation for:

- exploratory airfoil studies
- AI-guided aerodynamic iteration
- educational use around airfoil behavior
- rapid concept evaluation for 2D sections

## Runtime Requirements

Based on the current repository, ADA expects:

- Python package installation through `setup.py`
- a local `xfoil` executable available on `PATH`
- the `timelimit` utility
- UI assets copied into `~/.ada`
- environment variables for model access when using OpenAI

## Short Summary

ADA is an **AI-assisted airfoil design and analysis environment**. Its strongest current capability is a **natural-language workflow for building, modifying, running, and visualizing XFOIL-based airfoil studies** through a local browser UI.
