# Packet 4-DS-R Addendum — Chart Defects

Applies alongside `PACKET-4DSR-SECTION7-DEFECTS.md`. Same constraints: presentation only, targeted edits, iteration gate of typecheck + build + recapture, full gate once at the end, no commit.

Owner review of `sc4-insights-first-viewport-fixture.png`. The chart is a real Chart.js implementation but still reads as amateur. Six defects.

---

## G1. Y-axis floor at zero flattens the data

The axis runs 0–200 while the series lives between roughly 100 and 190. Half the plot is empty fill, and all real variation is compressed into the top third. A 90-point swing renders as a shallow diagonal.

Trend charts of this kind anchor near the data floor rather than zero. Implement a floor rule: begin the axis below the series minimum with a sensible margin, snapped to a round number, so the shape of the data is legible. State the rule you implement.

Where a zero baseline is genuinely required for honest interpretation of a specific metric, say which metrics those are and why, rather than applying zero everywhere by default.

## G2. The fill is flat, not a gradient — verify against pixels

The Section 4 report stated the fill is "a real canvas gradient, #184F3B at approximately 24% opacity at the top, fading to transparent at the baseline." The rendered image shows a uniform grey-green from the line to the axis with no visible falloff.

Determine whether the gradient is being created and applied at all, and whether it survives responsive resize — a canvas gradient built before the canvas has its final dimensions renders flat. Fix it, then verify by inspecting the rendered output, not by reading the configuration.

The current fill also reads muddy. Make it a deliberate tint that supports the line rather than an opacity applied to the line color.

## G3. The x-axis is boxed off like a table footer

The date labels sit below a horizontal rule in their own band, which makes the bottom of the chart read as a table footer. Remove the enclosing rule and let the labels sit directly beneath the plot.

## G4. No vertical gridlines

Six date labels with nothing connecting them to the plot. Add subtle vertical gridlines at the labeled dates, weighted below the horizontal grid so they organize without competing.

## G5. The plot is a minority of its own card

The card is roughly 340px tall and the plot occupies about 180px; the title and metric chips consume the rest. Rebalance so the plot is the dominant element — tighten the header and chip row, and give the plot the space.

## G6. The line has no presence

A thin hairline over a large flat fill. The trend line should carry the visual weight and the fill should support it. Increase the line weight and contrast against the fill accordingly.

---

## Acceptance

Recapture the Insights first-viewport and trend screenshots and the SEO screenshot, since SEO consumes the same component.

For G2 specifically, state how you verified the gradient renders — inspecting configuration is not verification.
