<!-- Test fixture: renders the real library elements with Svelte 5 event attributes. -->
<script lang="ts">
  import type { LeaderboardEntry, LeaderboardRowSelectDetail, ProgressCardActionDetail } from '@teampulse/ui-components';

  interface Props {
    rows: LeaderboardEntry[];
    onrow: (detail: LeaderboardRowSelectDetail) => void;
    onaction: (detail: ProgressCardActionDetail) => void;
  }

  let { rows, onrow, onaction }: Props = $props();
</script>

<tp-leaderboard-table entries={rows} highlightMe={true} ontp-row-select={(e) => onrow(e.detail)}></tp-leaderboard-table>
<tp-progress-card heading="Probe" actionLabel="Mark complete" ontp-action={(e) => onaction(e.detail)}></tp-progress-card>
