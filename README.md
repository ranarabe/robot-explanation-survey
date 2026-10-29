# Robot Explanation Study — GitHub Pages pilot

This is a buildless static survey. It needs no Python server, ROS2, or explanation engine, so it can be published directly on GitHub Pages.

For local testing, open `index.html` in a browser or run any simple static server from this folder.

## Add the study videos

The current prototype uses `assets/study-demo.mp4` in every video stage and plays it at 2× speed. To replace it, overwrite that file with another video.

Each video step also lets you choose a different local video file for the current session if needed.

## Robot answers in this pilot

Robot-question pages currently use prepared local answers in `app.js`. The participant’s question, prepared answer, and relevance rating are saved in the browser and shown in the researcher dashboard. The answer source can later be replaced by an API or ROS2 integration without changing the survey flow.

The welcome page includes `assets/robot-mascot.png`. The reward character sheet is `assets/dinosaur-characters.png` and contains 20 selectable dinosaur characters. The study now includes four stages: baseline, contrastive, counterfactual, and mixed contrastive/counterfactual. It collects survey language, gender, age, education, and (for university participants) whether they studied a technology/robotics-related field.

Each browser session has a participant ID such as `P-20261026-AB12C`. Responses and profile data are autosaved in `localStorage`. The participant does not see the data or export controls; the researcher can use the small **Researcher dashboard** link at the bottom of the survey or open `dashboard.html` directly to review records.
