# tp-progress-ring



<!-- Auto Generated Below -->


## Overview

Circular progress indicator (ARIA `progressbar`).

## Properties

| Property      | Attribute      | Description                                                                                              | Type                                                                                                                                                | Default      |
| ------------- | -------------- | -------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| `label`       | `label`        | Accessible name announced by assistive technology.                                                       | `string`                                                                                                                                            | `'Progress'` |
| `max`         | `max`          | Value that represents 100 %.                                                                             | `number`                                                                                                                                            | `100`        |
| `size`        | `size`         | Outer diameter in CSS pixels.                                                                            | `number`                                                                                                                                            | `120`        |
| `strokeWidth` | `stroke-width` | Thickness of the ring in CSS pixels.                                                                     | `number`                                                                                                                                            | `10`         |
| `tone`        | `tone`         | Colour tone: `primary \| success \| warning \| danger \| neutral` or a category (`fitness`, `sleep`, …). | `"danger" \| "fitness" \| "hydration" \| "learning" \| "mindfulness" \| "neutral" \| "nutrition" \| "primary" \| "sleep" \| "success" \| "warning"` | `'primary'`  |
| `value`       | `value`        | Current value.                                                                                           | `number`                                                                                                                                            | `0`          |


## Slots

| Slot | Description                                         |
| ---- | --------------------------------------------------- |
|      | Centre content. Defaults to the rounded percentage. |


## Shadow Parts

| Part       | Description                                  |
| ---------- | -------------------------------------------- |
| `"center"` | Wrapper of the centre content.               |
| `"ring"`   | The element carrying the `progressbar` role. |


----------------------------------------------

*Part of @teampulse/ui-components*
