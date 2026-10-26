# assets/

Visuals used in the top-level README.

- `mockup_*.svg` — design mockups of the UI (committed so the README has visuals
  even before deployment).

## Replacing mockups with real screenshots
1. Run the app: `streamlit run streamlit_app/app.py`
2. Run a review, then capture each tab (Decision brief, Review prep, Stakeholders).
3. Save them here as `screenshot_decision_brief.png`, `screenshot_review_prep.png`,
   `screenshot_stakeholders.png`.
4. In the top-level `README.md`, change the three image paths in the **Screenshots**
   section from `assets/mockup_*.svg` to your `assets/screenshot_*.png`.
