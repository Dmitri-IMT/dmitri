# 37signals Design Principles — Reference

Working reference for the UI design work (DMI-54 era): 37signals' UI and product design principles, verified against primary sources only, to inform how we breadboard, wireframe and scope the Dmitri web frontend (flows: [FLOWS.md](FLOWS.md); screen specs: [SCREENS.md](SCREENS.md); parking lot: [IDEAS.md](IDEAS.md)).

Every claim below links to the first-party source that owns it: Getting Real (Fried/DHH/Linderman, hosted at basecamp.com/gettingreal), Shape Up (Ryan Singer, basecamp.com/shapeup), and 37signals' published principles (37signals.com).

## Principles

### 1. Interface first

Design the screens before writing code. Design is cheap to change; code is not — and the interface is the part the customer actually experiences.

> "Design is relatively light. A paper sketch is cheap and easy to change... That's not true of programming."
>
> "The interface is your product. What people see is what you're selling."

Source: Getting Real, [Interface First](https://basecamp.com/gettingreal/09.1-interface-first)

### 2. Epicenter design

Start each page from the one thing it cannot live without, then build outward. Navigation, headers, sidebars and footers come last — never first.

> "Whatever the page absolutely can't live without is the epicenter. For example, if you're designing a page that displays a blog post, the blog post itself is the epicenter."

Source: Getting Real, [Epicenter Design](https://basecamp.com/gettingreal/09.2-epicenter-design)

### 3. Build less / half, not half-assed

Underdo the competition: ship fewer things, done completely. When forced to cut, cut features — not quality.

> "Instead of one-upping, try one-downing. Instead of outdoing, try underdoing." — [Build Less](https://basecamp.com/gettingreal/02.1-build-less)
>
> "Take whatever you think your product should be and cut it in half. Pare features down until you're left with only the most essential ones." — [Half, Not Half-Assed](https://basecamp.com/gettingreal/05.1-half-not-half-assed)

The code-side corollary: every line added grows complexity more than linearly, so the best design decisions are omissions ("the 'secret' to good software design wasn't in knowing what to put into the code; it was in knowing what to leave OUT!" — [Less Software](https://basecamp.com/gettingreal/10.1-less-software)).

### 4. Fixed time, variable scope / appetite

Fix the deadline and budget; flex what gets built. Shape Up formalizes this as an *appetite* — decide how much time a problem is worth before designing, instead of designing first and estimating after.

> "Never throw more time or money at a problem, just scale back the scope." — Getting Real, [Fix Time and Budget, Flex Scope](https://basecamp.com/gettingreal/02.4-fix-time-and-budget-flex-scope)
>
> "Appetites start with a number and end with a design. Estimates start with a design and end with a number." — Shape Up, [Set Boundaries](https://basecamp.com/shapeup/1.2-chapter-03)

"Good" is relative to the appetite: a solution is judged against the time it deserved, not against an ideal. When deciding whether something is done, Shape Up says to compare down to *baseline* — what customers have today — not up to the perfect version, and to "scope hammer" aggressively near the end ([Decide When to Stop](https://basecamp.com/shapeup/3.5-chapter-14)).

### 5. Decide at the right fidelity: breadboarding and fat-marker sketches

Shape design work at a level of abstraction that is concrete enough to argue about but rough enough to leave room. Two tools:

| Tool | What it fixes | What it deliberately leaves open |
| --- | --- | --- |
| Breadboard | Places (screens/dialogs), affordances (buttons/fields), connection lines between them | All layout and visual design |
| Fat-marker sketch | 2D arrangement of elements on a screen | All detail — the thick marker makes detail "difficult or impossible" |

Naming the rough stage and using a specific tool for it stops teams from "skipping ahead to the wrong level of fidelity" — jumping into wireframes before surveying enough options.

Source: Shape Up, [Find the Elements](https://basecamp.com/shapeup/1.3-chapter-04). Getting Real says the same about sequencing: "Work from large to small. Always." — [Ignore Details Early On](https://basecamp.com/gettingreal/04.2-ignore-details-early-on)

### 6. Copywriting is interface design

Labels, button text, error messages and empty-state copy are design decisions, not decoration. Write them in the user's language, not the system's.

> "Copywriting is interface design. Great interfaces are written." / "Every letter matters."

Source: Getting Real, [Copywriting is Interface Design](https://basecamp.com/gettingreal/09.7-copywriting-is-interface-design)

Related: design with real content, never lorem ipsum — "Dummy text means you won't see the inevitable variations that show up once real information is entered." ([Use Real Words](https://basecamp.com/gettingreal/11.4-use-real-words))

### 7. Design all three states: regular, blank, error

Every screen has three states and each must be designed deliberately:

| State | Definition (verbatim) |
| --- | --- |
| Regular | "The screen people see when everything's working fine and your app is flush with data." |
| Blank | "The screen people see when using the app for the first time, before data is entered." |
| Error | "The screen people see when something goes wrong." |

Source: Getting Real, [Three State Solution](https://basecamp.com/gettingreal/09.3-three-state-solution)

The blank slate is the first impression and is usually neglected because teams design with test data:

> "When you fail to design an adequate blank slate, people don't know what they are missing because everything is missing."

Source: Getting Real, [The Blank Slate](https://basecamp.com/gettingreal/09.4-the-blank-slate)

And failure states are where trust is won or lost:

> "Your app may work great 90% of the time. But if you abandon customers in their time of need, they're unlikely to forget it."

Source: Getting Real, [Get Defensive](https://basecamp.com/gettingreal/09.5-get-defensive)

### 8. Opinionated software: say no, avoid preferences

The product has a point of view; it makes decisions instead of exporting them to a settings page. Feature requests default to no — the ones that matter keep coming back.

> "The best software has a vision. The best software takes sides." — [Make Opinionated Software](https://basecamp.com/gettingreal/04.6-make-opinionated-software)
>
> "The secret to building half a product instead of a half-ass product is saying no." — [Start With No](https://basecamp.com/gettingreal/05.3-start-with-no)
>
> "Preferences are a way to avoid making tough decisions." — [Avoid Preferences](https://basecamp.com/gettingreal/06.4-avoid-preferences)

37signals still publishes "Know no" and "Disagree and commit" among its current numbered principles ([37signals.com](https://37signals.com/)).

### 9. Context over consistency

Give each page just what it needs to advance the user's next step, even if that breaks uniformity across screens.

> "It's ok to be inconsistent if your design makes more sense that way. Give people just what matters."

Source: Getting Real, [Context Over Consistency](https://basecamp.com/gettingreal/09.6-context-over-consistency). Also a current 37signals principle ("Context > consistency", [37signals.com](https://37signals.com/)).

### 10. Zero training

The UI should need no manual. Clarity beats cleverness; inline help sits exactly where people struggle, not in a separate docs silo.

> "Strive to build a tool that requires zero training."

Source: Getting Real, [Zero Training](https://basecamp.com/gettingreal/14.2-zero-training)

### 11. One interface

Don't build a separate admin application. Fold administrative functions into the main interface — two interfaces means double the surface to design and both get worse.

Source: Getting Real, [One Interface](https://basecamp.com/gettingreal/09.8-one-interface)

### 12. It's a problem when it's a problem

Don't design for hypothetical scale or hypothetical needs. Decide just-in-time, with real information.

> "Don't waste time on problems you don't have yet."

Source: Getting Real, [It's a Problem When It's a Problem](https://basecamp.com/gettingreal/04.3-its-a-problem-when-its-a-problem)

### 13. Get one piece done (vertical slices)

When building starts, integrate one small end-to-end slice (design + code, front to back) first, instead of finishing horizontal layers.

> "Integrate vertically on one small piece of the project instead of chipping away at the horizontal layers."

Source: Shape Up, [Get One Piece Done](https://basecamp.com/shapeup/3.2-chapter-11)

## Applying this to Dmitri

How these map onto the upcoming frontend wireframes (React 19 SPA, shadcn/ui, desktop-first; roles: non-technical org admin + read-only viewer).

| Principle | Application |
| --- | --- |
| Interface first (1) | Wireframe every screen before any React code; the wireframes doc is the contract, not an afterthought. |
| Epicenter design (2) | The dashboard is a review, and its epicenter = the verdict line — whether anything needs the operator's attention ([SCREENS.md](SCREENS.md) §Dashboard). Scan detail epicenter = findings list. Agents screen epicenter = agent status + "Scan now". Design chrome last. |
| Half, not half-assed (3) | MVP = read UI + "Scan now" trigger, done well. No LLM analysis panel, no report builder, no notification center — a complete half, not a sketchy whole. |
| Appetite (4) | Timebox each screen's design. When a screen runs over, cut scope (e.g. drop filters from host inventory v1), never quality of what remains. Compare to baseline: today users have no web UI at all. |
| Right fidelity (5) | Breadboard the flows first (login → dashboard → scan detail; Agents → Scan now → poll status), fat-marker the layouts, and only then write ASCII wireframes. Don't debate paddings in a breadboard. |
| Copywriting (6) | Write the real copy in the wireframes: "Pi seems to be offline", "Scan started — this usually takes about 10 minutes", "No critical findings". Buttons say what they do ("Scan now", not "Execute"). Use real hostnames/CVEs in mocks, never lorem ipsum. |
| Three states + blank slate (7) | Every screen ships with regular/blank/error designed. "No scans yet" on the dashboard must explain what a scan is and point at "Scan now" — the blank slate is the onboarding. Error state for a dead Pi is a first-class design, not a toast afterthought. |
| Opinionated, no preferences (8) | Two roles, fixed severity colors, one default scan mode surfaced. No settings page in the MVP; the product decides. Feature requests start at no. |
| Context over consistency (9) | The read-only viewer's dashboard can omit "Scan now" entirely rather than showing a disabled button; each page shows just what advances that user's next step. |
| Zero training (10) | The org admin is non-technical: severity badges over CVSS vectors, plain-language finding summaries, inline hint where confusion is likely (e.g. what "agent last seen" means). |
| One interface (11) | User management lives inside the same AppShell as everything else — an admin nav item, not a second app. |
| Problem when it's a problem (12) | No pagination-for-thousands, multi-org tenancy UI, or mobile layout until real usage demands them. |
| One piece done (13) | First build slice: login → dashboard with live severity counts, end to end, before touching the other screens. |
