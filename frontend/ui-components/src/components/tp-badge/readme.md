# tp-badge



<!-- Auto Generated Below -->


## Overview

Achievement badge — earned (with award date) or locked.

## Properties

| Property      | Attribute     | Description                                    | Type      | Default |
| ------------- | ------------- | ---------------------------------------------- | --------- | ------- |
| `awardedAt`   | `awarded-at`  | Award timestamp (ISO date or datetime).        | `string`  | `''`    |
| `compact`     | `compact`     | Compact layout (icon + name only).             | `boolean` | `false` |
| `description` | `description` | What the badge is awarded for.                 | `string`  | `''`    |
| `icon`        | `icon`        | Emoji or short text rendered inside the medal. | `string`  | `'🏅'`  |
| `locked`      | `locked`      | Renders the badge greyed out with a lock.      | `boolean` | `false` |
| `name`        | `name`        | Badge name.                                    | `string`  | `''`    |


## Shadow Parts

| Part      | Description          |
| --------- | -------------------- |
| `"badge"` | The badge container. |
| `"medal"` | The circular icon.   |


----------------------------------------------

*Part of @teampulse/ui-components*
