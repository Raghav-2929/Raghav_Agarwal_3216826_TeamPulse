# tp-stat-tile



<!-- Auto Generated Below -->


## Overview

Key-figure tile (KPI) with optional delta and hint.

## Properties

| Property      | Attribute      | Description                                                                    | Type                            | Default     |
| ------------- | -------------- | ------------------------------------------------------------------------------ | ------------------------------- | ----------- |
| `delta`       | `delta`        | Change vs. a previous period: a number (`3`, `-2`) or display string (`+12%`). | `number \| string \| undefined` | `undefined` |
| `hint`        | `hint`         | Secondary explanatory text.                                                    | `string`                        | `''`        |
| `invertDelta` | `invert-delta` | Inverts colouring when a decrease is good (e.g. "suppressed days").            | `boolean`                       | `false`     |
| `label`       | `label`        | What the figure measures.                                                      | `string`                        | `''`        |
| `value`       | `value`        | The figure itself (number or pre-formatted string).                            | `number \| string`              | `''`        |


## Slots

| Slot     | Description                             |
| -------- | --------------------------------------- |
|          | Extra content rendered after the value. |
| `"icon"` | Icon rendered next to the label.        |


## Shadow Parts

| Part      | Description         |
| --------- | ------------------- |
| `"tile"`  | The tile container. |
| `"value"` | The value element.  |


----------------------------------------------

*Part of @teampulse/ui-components*
