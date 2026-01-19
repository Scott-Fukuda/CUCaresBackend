from operator import and_
from flask import Blueprint, jsonify, make_response, request, Response
from utils.auth import require_auth
from db import db, User, Opportunity, UserOpportunity
import io, csv
from sqlalchemy import select
from datetime import date, timedelta

service_bp = Blueprint("service", __name__)

# SERVICE JOURNAL ENDPOINTS
@service_bp.route('/api/service-journal/opps/<int:user_id>', methods=['GET'])
@require_auth
def service_opps(user_id):
    # Query only the columns you need — no model overhead
    rows = (
        db.session.query(
            Opportunity.id,
            Opportunity.name,
            Opportunity.date,
            UserOpportunity.driving,
            Opportunity.host_user_id,
            Opportunity.duration,
            UserOpportunity.attended
        )
        .join(UserOpportunity, UserOpportunity.opportunity_id == Opportunity.id)
        .filter(UserOpportunity.user_id == user_id)
        .all()
    )

    # Convert results to JSON-serializable dicts
    result = [
        {
            "id": id,
            "name": name,
            "date": date,
            "driver": driving,
            "host": (host_user_id == user_id),
            "duration": duration,
            "attended": attended
        }
        for id, name, date, driving, host_user_id, duration, attended in rows
    ]

    return jsonify(result), 200

@service_bp.route('/api/service-journal/opps/<int:user_id>/csv', methods=['GET'])
@require_auth
def service_opps_csv(user_id):
    """
    Return opportunities as CSV attachment with requested columns.
    """
    # Query only the needed columns efficiently
    stmt = (
        select(
            Opportunity.id,
            Opportunity.name,
            Opportunity.date,
            UserOpportunity.driving,
            Opportunity.host_user_id,
            Opportunity.duration,
            UserOpportunity.attended
        )
        .join(UserOpportunity, UserOpportunity.opportunity_id == Opportunity.id)
        .filter(UserOpportunity.user_id == user_id)
    )
    rows = db.session.execute(stmt).all()

    # Create an in-memory CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "date", "driver", "host", "duration", "attended"])  # header row

    for id, name, date, driving, host_user_id, duration, attended in rows:
        writer.writerow([
            id,
            name,
            date.isoformat() if date else "",
            "true" if driving else "false",
            "host" if host_user_id == user_id else "participant",
            duration,
            "true" if attended else "false"
        ])

    csv_data = output.getvalue()
    output.close()

    # Build HTTP response
    response = make_response(csv_data)
    
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; ffilename=service_opps_user_{user_id}.csv'

    return response


@service_bp.route("/api/service-data/org/", methods=["POST"])
@require_auth
def org_service_data_csv():
    data = request.get_json()
    start_date = date.fromisoformat(data["start_date"])
    end_date = date.fromisoformat(data["end_date"])

    # Align to full week range (Mon–Sun)
    start_date -= timedelta(days=start_date.weekday())
    end_date += timedelta(days=(6 - end_date.weekday()))

    # Get all attended user–opportunity pairs in the range
    rows = (
        db.session.query(
            User.id.label("user_id"),
            Opportunity.date.label("date"),
            Opportunity.duration.label("duration")
        )
        .join(UserOpportunity, User.id == UserOpportunity.user_id)
        .join(Opportunity, Opportunity.id == UserOpportunity.opportunity_id)
        .filter(
            and_(
                UserOpportunity.attended == True,
                Opportunity.date >= start_date,
                Opportunity.date <= end_date
            )
        )
        .all()
    )

    # Get mapping of user → orgs (to avoid querying repeatedly)
    user_org_map = {
        u.id: [(org.id, org.name) for org in u.organizations]
        for u in db.session.query(User).options(db.joinedload(User.organizations)).all()
    }

    # Define weekly bins
    num_weeks = ((end_date - start_date).days // 7) + 1
    week_bins = [
        (start_date + timedelta(days=i*7), start_date + timedelta(days=i*7 + 6))
        for i in range(num_weeks)
    ]
    week_labels = [f"{ws:%b %d}–{we:%b %d}" for ws, we in week_bins]

    # Aggregate totals: {org_id: {week_label: total_hours}}
    table = {}

    for row in rows:
        user_orgs = user_org_map.get(row.user_id, [])
        for (week_start, week_end) in week_bins:
            if week_start <= row.date.date() <= week_end:
                week_label = f"{week_start:%b %d}–{week_end:%b %d}"
                for org_id, org_name in user_orgs:
                    table.setdefault((org_id, org_name), {}).setdefault(week_label, 0)
                    table[(org_id, org_name)][week_label] += row.duration
                break

    # --- Build CSV ---
    output = io.StringIO()
    writer = csv.writer(output)
    header = ["Organization ID", "Organization Name"] + week_labels
    writer.writerow(header)

    for (org_id, org_name), weekly_data in table.items():
        row = [org_id, org_name]
        for label in week_labels:
            row.append(round(weekly_data.get(label, 0), 2))
        writer.writerow(row)

    csv_data = output.getvalue()
    output.close()

    filename = f"org_service_data_{start_date:%Y%m%d}_{end_date:%Y%m%d}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
