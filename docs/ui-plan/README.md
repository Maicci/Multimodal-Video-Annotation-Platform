# Administrator and annotator UI proposal

These are single-frame desktop mockups for customer feedback. The example
videos, counts, names, and status values are illustrative. The HTML files are
static previews, not application screens.

## Administrator view

![Administrator video library proposal](admin.png)

The proposed library keeps upload, transfer progress, processing status, and
the video list on one screen. Transfer progress and background processing are
shown separately so that 100% uploaded does not imply the video is ready.

## Annotator view

![Annotator workspace proposal](annotator.png)

The proposed workspace places video playback next to the segment list. The
timeline and draggable start/end handles sit directly below the player, with
the selected segment's fields alongside them.

## Questions for customer feedback

1. Is the administrator's upload and video list layout clear enough for daily use?
2. Should annotators see only assigned videos, or the full library?
3. Are video, segment list, timeline, and details in the right places for annotation work?
4. Which segment fields are required beyond title, time range, and description?
5. Should administrators and annotators have different controls on the video page?

Search, filters, team invitations, assignment navigation, and saved-state
indicators in these pictures are proposals. They are not claims that those
features are implemented. Open `admin.html` or `annotator.html` locally to
inspect the static layout at full size.
