"""GeoShield – Intelligence Assistant Blueprint
Answers natural language queries strictly using actual real-time & historical NASA VIIRS datasets.
No fake statistics or hallucinations.
"""
import re
import logging
from flask import Blueprint, render_template, jsonify, request, session
from routes.auth import login_required
from services.data_service import get_df, get_city_summary
from services.event_fusion import fuse_events

assistant_bp = Blueprint("assistant", __name__)
log = logging.getLogger("GeoShield.Assistant")


@assistant_bp.route("/assistant")
@login_required
def assistant_page():
    return render_template("assistant.html", user=session.get("user"))


@assistant_bp.route("/api/assistant", methods=["POST"])
@login_required
def api_query_assistant():
    try:
        data = request.get_json() or {}
        user_query = data.get("query", "").strip()

        if not user_query:
            return jsonify({"error": "Query cannot be empty"}), 400

        df = get_df()
        q_lower = user_query.lower()

        # Engine to process data-backed intelligence queries
        response_data = {
            "query": user_query,
            "answer": "",
            "metrics": {},
            "records": [],
            "source": "NASA VIIRS JPSS-1 (India Dataset 2022-2024)"
        }

        # 1. Query: Highest fire activity / which cities or states
        if any(w in q_lower for w in ["highest fire", "top fire", "most fire", "which city", "which states"]):
            cities = get_city_summary(df)
            top5 = cities[:5]
            response_data["answer"] = (
                f"Based on real NASA VIIRS satellite records across India (2022–2024), "
                f"the city with the highest recorded fire detections is **{top5[0]['city']}** "
                f"with **{top5[0]['fire']:,}** fire detections and an average FRP of **{top5[0]['avg_frp']} MW**. "
                f"Here are the top 5 impacted areas:"
            )
            response_data["records"] = top5
            response_data["metrics"] = {
                "Top City": top5[0]['city'],
                "Detections": f"{top5[0]['fire']:,}",
                "Avg FRP": f"{top5[0]['avg_frp']} MW"
            }

        # 2. Query: Flood detections / flood in 2024
        elif "flood" in q_lower:
            year_match = re.search(r"\b(2022|2023|2024)\b", q_lower)
            if year_match:
                target_year = int(year_match.group(1))
                flood_sub = df[(df["label"] == 2) & (df["year"] == target_year)]
                total_in_yr = len(df[df["year"] == target_year])
                pct = round(len(flood_sub) / total_in_yr * 100, 2) if total_in_yr else 0
                response_data["answer"] = (
                    f"In **{target_year}**, GeoShield recorded **{len(flood_sub):,} flood-proxy detections** "
                    f"in India ({pct}% of all {target_year} satellite observations). "
                    f"Average brightness temperature was **{flood_sub['brightness'].mean():.1f} K**."
                )
                response_data["metrics"] = {
                    "Year": target_year,
                    "Flood Detections": f"{len(flood_sub):,}",
                    "Percentage": f"{pct}%"
                }
            else:
                total_floods = int((df["label"] == 2).sum())
                response_data["answer"] = (
                    f"Across the full 2022–2024 dataset, there are **{total_floods:,} total flood-proxy detections** "
                    f"documented by VIIRS infrared anomalies with FRP < 5 MW and brightness < 320 K."
                )
                response_data["metrics"] = {"Total Flood Events": f"{total_floods:,}"}

        # 3. Query: High-risk incidents / critical incidents
        elif any(w in q_lower for w in ["high-risk", "high risk", "critical", "severe", "priority"]):
            inc = fuse_events(df, event_type="all")
            high_inc = inc[inc["risk_level"].isin(["CRITICAL", "HIGH"])].head(6)
            response_data["answer"] = (
                f"Event Fusion identified **{len(high_inc)} high-priority disaster incidents** "
                f"requiring immediate responder focus. The highest scoring cluster has risk score "
                f"**{high_inc.iloc[0]['risk_score']}/100** located near **{high_inc.iloc[0].get('city','Unknown')}**."
            )
            records = []
            for _, r in high_inc.iterrows():
                records.append({
                    "event_id": r["event_id"],
                    "city": r.get("city", "Unknown"),
                    "type": r["event_type"],
                    "risk_score": r["risk_score"],
                    "max_frp": f"{r['max_frp']} MW",
                    "detections": r["detection_count"]
                })
            response_data["records"] = records
            response_data["metrics"] = {
                "Top Event ID": high_inc.iloc[0]['event_id'],
                "Risk Score": f"{high_inc.iloc[0]['risk_score']}/100",
                "Max FRP": f"{high_inc.iloc[0]['max_frp']} MW"
            }

        # 4. Query: Longest persistence / duration
        elif any(w in q_lower for w in ["persistence", "duration", "longest", "days"]):
            inc = fuse_events(df, event_type="all")
            persistent = inc.sort_values("duration_days", ascending=False).head(5)
            response_data["answer"] = (
                f"The disaster event with the highest persistence is Incident **#{persistent.iloc[0]['event_id']}** "
                f"near **{persistent.iloc[0].get('city','Unknown')}**, which remained active for "
                f"**{persistent.iloc[0]['duration_days']} consecutive days** with {persistent.iloc[0]['detection_count']} detections."
            )
            records = []
            for _, r in persistent.iterrows():
                records.append({
                    "event_id": r["event_id"],
                    "city": r.get("city", "Unknown"),
                    "duration_days": r["duration_days"],
                    "detections": r["detection_count"],
                    "risk_score": r["risk_score"]
                })
            response_data["records"] = records
            response_data["metrics"] = {
                "Max Duration": f"{persistent.iloc[0]['duration_days']} Days",
                "Event ID": persistent.iloc[0]['event_id']
            }

        # 5. Query: Specific city (e.g. Indore, Delhi, Guwahati, Mumbai, etc.)
        else:
            # Check if any known city is mentioned
            cities_in_df = df["city"].unique().tolist() if "city" in df.columns else []
            matched_city = None
            for c in cities_in_df:
                if c and c.lower() in q_lower:
                    matched_city = c
                    break

            if matched_city:
                c_df = df[df["city"] == matched_city]
                fire_c = int((c_df["label"] == 1).sum())
                flood_c = int((c_df["label"] == 2).sum())
                max_frp = float(c_df["frp"].max()) if not c_df.empty else 0.0
                response_data["answer"] = (
                    f"Records for **{matched_city}**:\n"
                    f"• Total detections: **{len(c_df):,}**\n"
                    f"• Fire events: **{fire_c:,}**\n"
                    f"• Flood proxy events: **{flood_c:,}**\n"
                    f"• Maximum Fire Radiative Power (FRP): **{max_frp:.1f} MW**\n"
                    f"• Observation dates: {str(c_df['acq_date'].min())[:10]} to {str(c_df['acq_date'].max())[:10]}."
                )
                response_data["metrics"] = {
                    "City": matched_city,
                    "Total Events": f"{len(c_df):,}",
                    "Fire Detections": f"{fire_c:,}",
                    "Max FRP": f"{max_frp:.1f} MW"
                }
            else:
                # Default intelligent summary
                total_events = len(df)
                total_fire = int((df["label"] == 1).sum())
                total_flood = int((df["label"] == 2).sum())
                response_data["answer"] = (
                    f"GeoShield Intelligence Assistant has access to **{total_events:,} verified NASA VIIRS detections** "
                    f"across India ({total_fire:,} Fire, {total_flood:,} Flood events). "
                    f"You can ask me questions like:\n"
                    f"• 'Which cities have the highest fire activity?'\n"
                    f"• 'How many flood detections occurred in 2024?'\n"
                    f"• 'Show high-risk disaster incidents.'\n"
                    f"• 'Which incidents have the highest persistence?'\n"
                    f"• 'What is the fire situation in Indore or Guwahati?'"
                )
                response_data["metrics"] = {
                    "Total Detections": f"{total_events:,}",
                    "Fire Events": f"{total_fire:,}",
                    "Flood Events": f"{total_flood:,}"
                }

        return jsonify(response_data)

    except Exception as e:
        log.exception("assistant query error")
        return jsonify({"error": str(e)}), 500
