# tp-leaderboard-table



<!-- Auto Generated Below -->


## Overview

Ranked leaderboard for challenges, in individual or team mode.
Rows are keyboard-navigable (↑/↓/Home/End) and selectable (click, Enter, Space).

## Properties

| Property      | Attribute      | Description                                                                                                                                                                                                                                        | Type                                                     | Default                  |
| ------------- | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- | ------------------------ |
| `caption`     | `caption`      | Accessible caption for the table (visually hidden).                                                                                                                                                                                                | `string`                                                 | `'Leaderboard'`          |
| `emptyText`   | `empty-text`   | Message shown when there are no rows.                                                                                                                                                                                                              | `string`                                                 | `'No participants yet.'` |
| `entries`     | `entries`      | Rows to render. Accepts an array (set as a JS property) or a JSON string (attribute). Individual rows: `{rank, display_name, team_name?, score, goal_reached?, is_me?}`. Team rows: `{rank, team_name, participants, total_score, average_score}`. | `LeaderboardEntry[] \| TeamLeaderboardEntry[] \| string` | `[]`                     |
| `highlightMe` | `highlight-me` | Highlights the row flagged `is_me` (individual mode).                                                                                                                                                                                              | `boolean`                                                | `true`                   |
| `mode`        | `mode`         | `individual` or `team`.                                                                                                                                                                                                                            | `"individual" \| "team"`                                 | `'individual'`           |
| `scoreLabel`  | `score-label`  | Header of the score column in individual mode.                                                                                                                                                                                                     | `string`                                                 | `'Score'`                |


## Events

| Event           | Description                                                                                                     | Type                                      |
| --------------- | --------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| `tp-row-select` | Emitted when a row is activated by click, Enter or Space. Listen in Svelte 5 with `ontp-row-select={(e) => …}`. | `CustomEvent<LeaderboardRowSelectDetail>` |


## Slots

| Slot        | Description                                                          |
| ----------- | -------------------------------------------------------------------- |
| `"actions"` | Controls rendered at the end of the header bar (e.g. a mode switch). |
| `"caption"` | Heading content rendered above the table (e.g. a title).             |


## Shadow Parts

| Part      | Description            |
| --------- | ---------------------- |
| `"row"`   | Each body row.         |
| `"table"` | The `<table>` element. |


----------------------------------------------

*Part of @teampulse/ui-components*
