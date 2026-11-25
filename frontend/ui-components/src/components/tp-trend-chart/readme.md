# tp-trend-chart



<!-- Auto Generated Below -->


## Overview

Dependency-free SVG line / bar chart for daily trends.

- `null` y values are rendered as gaps (lines break, bars are replaced by a hatched marker) —
  used for k-anonymity–suppressed days on team insights.
- Hover or focus a column to see a tooltip; ←/→/Home/End move between columns,
  Enter/Space (or click) emits `tp-point-select`.
- A visually hidden data table mirrors the chart for screen readers.

## Properties

| Property     | Attribute     | Description                                                                                                                          | Type                      | Default                      |
| ------------ | ------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------- | ---------------------------- |
| `emptyText`  | `empty-text`  | Message rendered when there is nothing to plot.                                                                                      | `string`                  | `'No data for this period.'` |
| `gapLabel`   | `gap-label`   | Text used for `null` points in tooltips and the data table.                                                                          | `string`                  | `'No data'`                  |
| `height`     | `height`      | Chart height in CSS pixels.                                                                                                          | `number`                  | `240`                        |
| `label`      | `label`       | Accessible name of the chart.                                                                                                        | `string`                  | `'Trend chart'`              |
| `series`     | `series`      | Series to plot. Array (JS property) or JSON string (attribute) of `{label, points: [{x: 'YYYY-MM-DD', y: number \| null}], color?}`. | `TrendSeries[] \| string` | `[]`                         |
| `showLegend` | `show-legend` | Shows the legend (always hidden for a single unlabeled series).                                                                      | `boolean`                 | `true`                       |
| `type`       | `type`        | `line` or `bar`.                                                                                                                     | `"bar" \| "line"`         | `'line'`                     |
| `yLabel`     | `y-label`     | Optional y-axis title.                                                                                                               | `string`                  | `''`                         |


## Events

| Event             | Description                                                                                                          | Type                                  |
| ----------------- | -------------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| `tp-point-select` | Emitted when a column is activated by click, Enter or Space. Listen in Svelte 5 with `ontp-point-select={(e) => …}`. | `CustomEvent<TrendPointSelectDetail>` |


## Shadow Parts

| Part        | Description            |
| ----------- | ---------------------- |
| `"legend"`  | The legend list.       |
| `"svg"`     | The chart `<svg>`.     |
| `"tooltip"` | The tooltip container. |


----------------------------------------------

*Part of @teampulse/ui-components*
