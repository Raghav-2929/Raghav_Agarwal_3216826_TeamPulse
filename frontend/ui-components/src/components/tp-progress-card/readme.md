# tp-progress-card



<!-- Auto Generated Below -->


## Overview

Card summarising progress on a habit, streak or goal, with an optional built-in action
button (e.g. "Mark complete").

## Properties

| Property         | Attribute         | Description                                                                  | Type                  | Default      |
| ---------------- | ----------------- | ---------------------------------------------------------------------------- | --------------------- | ------------ |
| `action`         | `action`          | Identifier sent in the `tp-action` event detail.                             | `string`              | `'complete'` |
| `actionLabel`    | `action-label`    | Label of the built-in action button. Leave empty to hide the button.         | `string`              | `''`         |
| `busy`           | `busy`            | Shows a busy state and disables the built-in action.                         | `boolean`             | `false`      |
| `category`       | `category`        | Activity type; drives the accent colour and default icon.                    | `string \| undefined` | `undefined`  |
| `completed`      | `completed`       | Whether the item is completed (for today / the period).                      | `boolean`             | `false`      |
| `completedLabel` | `completed-label` | Label shown on the built-in button once `completed` is true.                 | `string`              | `'Done'`     |
| `heading`        | `heading`         | Card title (named `heading` because `title` is a reserved global attribute). | `string`              | `''`         |
| `streak`         | `streak`          | Current streak length; hidden when `0`.                                      | `number`              | `0`          |
| `streakUnit`     | `streak-unit`     | Unit of the streak (`day` or `week`).                                        | `string`              | `'day'`      |
| `target`         | `target`          | Target value; when `0` no progress meter is shown.                           | `number`              | `0`          |
| `unit`           | `unit`            | Unit shown after the figures (e.g. `days`, `check-ins`).                     | `string`              | `''`         |
| `value`          | `value`           | Current progress value.                                                      | `number`              | `0`          |


## Events

| Event       | Description                                                                                             | Type                                    |
| ----------- | ------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| `tp-action` | Emitted when the built-in action button is activated. Listen in Svelte 5 with `ontp-action={(e) => …}`. | `CustomEvent<ProgressCardActionDetail>` |


## Slots

| Slot        | Description                                                                     |
| ----------- | ------------------------------------------------------------------------------- |
|             | Extra body content rendered under the heading.                                  |
| `"actions"` | Additional action controls rendered in the footer (before the built-in button). |
| `"icon"`    | Leading icon. Defaults to the category emoji.                                   |


## Shadow Parts

| Part       | Description                 |
| ---------- | --------------------------- |
| `"action"` | The built-in action button. |
| `"card"`   | The card container.         |


----------------------------------------------

*Part of @teampulse/ui-components*
