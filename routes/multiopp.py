import datetime
from operator import and_
import traceback
from flask import Blueprint, jsonify, make_response, request, Response
from utils.auth import require_auth
from db import db, Opportunity, MultiOpportunity
from services.carpool_service import add_carpool
import json

multiopp_bp = Blueprint("multiopp", __name__)

def generate_opportunities_from_multiopp(multiopp: MultiOpportunity, data: dict):
    """Generate individual opportunities from a MultiOpportunity recurrence pattern."""
    from datetime import datetime, timedelta
    import pytz

    all_opps = []
    start_date = multiopp.start_date

    eastern = pytz.timezone("US/Eastern")

    # Flatten day/time mapping list into (weekday, [(time_str, duration), ...]) pairs
    day_time_pairs = []
    for entry in multiopp.days_of_week:
        for weekday, time_list in entry.items():
            day_time_pairs.append((weekday, time_list))

    total_weeks = multiopp.week_recurrences or 4
    week_frequency = multiopp.week_frequency or 1

    for week_index in range(total_weeks):
        # Handle every Nth week (e.g., every 2 weeks)
        if week_frequency > 1 and week_index % week_frequency != 0:
            continue

        base_week_start = start_date + timedelta(weeks=week_index)

        for weekday_name, time_list in day_time_pairs:
            weekday_index = [
                "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
            ].index(weekday_name)
            day_date = base_week_start + timedelta(days=(weekday_index - base_week_start.weekday()) % 7)

            for time_entry in time_list:
                # Each entry is a tuple or list: (start_time_str, duration)
                if isinstance(time_entry, (list, tuple)) and len(time_entry) == 2:
                    start_time_str, duration = time_entry
                else:
                    start_time_str, duration = time_entry, 60

                # Parse "HH:MM" or ISO "T" time
                start_time = (
                    datetime.fromisoformat(start_time_str).time()
                    if "T" in start_time_str
                    else datetime.strptime(start_time_str, "%H:%M").time()
                )

                # Combine with date (naive datetime)
                naive_dt = datetime.combine(day_date.date(), start_time)

                # ✅ Localize to Eastern time, then convert to UTC for DB storage
                localized_dt = eastern.localize(naive_dt)
                dt_utc = localized_dt.astimezone(pytz.utc)
                allow_carpool = data.get('allow_carpool').lower() == "true"

                opp = Opportunity(
                    name=data["name"],
                    description=data.get("description"),
                    causes=data.get("causes", []),
                    tags=data.get("tags", []),
                    address=data["address"],
                    nonprofit=data.get("nonprofit"),
                    image=data.get("image"),
                    approved=data.get("approved", False),
                    host_org_name=data.get("host_org_name"),
                    qualifications=data.get("qualifications", []),
                    visibility=data.get("visibility", []),
                    host_org_id=data.get("host_org_id"),
                    host_user_id=data.get("host_user_id"),
                    redirect_url=data.get("redirect_url"),
                    total_slots=data.get("total_slots"),
                    allow_carpool=allow_carpool,

                    # Recurrence-specific fields
                    date=dt_utc,  # store in UTC
                    duration=duration,
                    recurring="recurring",
                    comments=[],
                    attendance_marked=False,
                    actual_runtime=None,

                    # Relationship
                    multiopp_id=multiopp.id,
                    multi_opportunity=multiopp,
                )

                db.session.add(opp)
                all_opps.append(opp)
                db.session.flush() 

                if allow_carpool:
                    add_carpool(opp, 'multiopp')

    db.session.commit()
    return all_opps

@multiopp_bp.route("/api/multiopps", methods=["POST"])
@require_auth
def create_multiopp():
    try: 
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
            # Parse JSON-like fields manually
            if "days_of_week" in data:
                data["days_of_week"] = json.loads(data["days_of_week"])
            if "week_frequency" in data:
                data["week_frequency"] = int(data["week_frequency"])
            if "week_recurrences" in data:
                data["week_recurrences"] = int(data["week_recurrences"])
            if "approved" in data:
                data["approved"] = data["approved"].lower() == "true"
            if "visibility" in data:
                data["visibility"] = json.loads(request.form["visibility"])


        # Step 1: Create MultiOpportunity (recurrence definition)
        multiopp = MultiOpportunity(
            name=data["name"],
            description=data.get("description"),
            causes=data.get("causes", []),
            tags=data.get("tags", []),
            address=data["address"],
            nonprofit=data.get("nonprofit"),
            image=data.get("image"),
            approved=data.get("approved", False),
            host_org_name=data.get("host_org_name"),
            qualifications=data.get("qualifications", []),
            visibility=data.get("visibility", []),
            host_org_id=data.get("host_org_id"),
            host_user_id=data.get("host_user_id"),
            redirect_url=data.get("redirect_url"),
            total_slots=data.get("total_slots"),
            start_date=datetime.fromisoformat(data["start_date"]),
            days_of_week=data["days_of_week"],
            week_frequency=data.get("week_frequency"),
            week_recurrences=data.get("week_recurrences", 4)
        )

        db.session.add(multiopp)
        db.session.commit()

        # Step 2: Generate the actual individual Opportunities
        generated_opps = generate_opportunities_from_multiopp(multiopp, data)

        # Step 3: Return serialized MultiOpportunity and its generated Opportunities
        return jsonify({
            "multiopp": multiopp.serialize(),
            "generated_opportunities": [opp.serialize() for opp in generated_opps]
        }), 201
    except Exception as e:
        db.session.rollback()
        print("Error in /api/multiopps:")
        traceback.print_exc()
        return jsonify({
            'message': 'Failed to create carpool',
            'error': str(e)
        }), 500

@multiopp_bp.route("/api/multiopps/<int:multiopp_id>", methods=["PUT"])
@require_auth
def update_multiopp(multiopp_id):
    """Update a MultiOpportunity and propagate changes to its opportunities"""
    try:
        multiopp = MultiOpportunity.query.get_or_404(multiopp_id)
        
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
            if "approved" in data:
                data["approved"] = data["approved"].lower() == "true"

        update_fields = ['name', 'description', 'address', 'nonprofit', 
                        'redirect_url']
        
        for field in update_fields:
            if field in data:
                setattr(multiopp, field, data[field])

        db.session.commit()

        opportunities = Opportunity.query.filter_by(multiopp_id=multiopp_id).all()
        
        for opp in opportunities:
            for field in update_fields:
                if field in data:
                    setattr(opp, field, data[field])
            
            db.session.flush()
            
            if not opp.allow_carpool and data["allow_carpool"]:
                setattr(opp,'allow_carpool', True)
                add_carpool(opp, 'multiopp')
        
        db.session.commit()
        
        return jsonify({
            "message": "MultiOpportunity and opportunities updated successfully",
            "multiopp": multiopp.serialize(),
            "updated_opportunities": [opp.serialize() for opp in opportunities]
        }), 200

    except Exception as e:
        db.session.rollback()
        print("Error in PUT /api/multiopps/<id>:")
        traceback.print_exc()
        return jsonify({
            'message': 'Failed to update MultiOpportunity',
            'error': str(e)
        }), 500

# 🟡 GET ALL multiopps
@multiopp_bp.route("/api/multiopps", methods=["GET"])
# @require_auth
def get_all_multiopps():
    multiopps = MultiOpportunity.query.all()
    return jsonify([m.serialize() for m in multiopps]), 200


# 🟢 GET SINGLE multiopp by ID
@multiopp_bp.route("/api/multiopps/<int:multiopp_id>", methods=["GET"])
@require_auth
def get_multiopp(multiopp_id):
    multiopp = MultiOpportunity.query.get_or_404(multiopp_id)
    return jsonify(multiopp.serialize()), 200


# 🔴 DELETE multiopp by ID
@multiopp_bp.route("/api/multiopps/<int:multiopp_id>", methods=["DELETE"])
@require_auth
def delete_multiopp(multiopp_id):
    multiopp = MultiOpportunity.query.get_or_404(multiopp_id)

    db.session.delete(multiopp)
    db.session.commit()
    return jsonify({"message": f"MultiOpportunity {multiopp_id} deleted successfully."})

@multiopp_bp.route("/api/multiopps/<int:multiopp_id>/visibility", methods=["PUT"])
@require_auth
def update_multiopp_visibility(multiopp_id):
    """Update only the visibility field of a MultiOpportunity."""
    data = request.get_json(force=True, silent=True)

    if not data or "visibility" not in data:
        return jsonify({"error": "Missing 'visibility' field in request body."}), 400

    multiopp = MultiOpportunity.query.get(multiopp_id)
    if not multiopp:
        return jsonify({"error": "MultiOpportunity not found."}), 404

    # Update visibility
    try:
        if isinstance(data["visibility"], str):
            multiopp.visibility = json.loads(data["visibility"])
        else:
            multiopp.visibility = data["visibility"]
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid format for 'visibility'. Must be JSON array or object."}), 400

    db.session.commit()

    return jsonify({"multiopp": multiopp.serialize()}), 200

@multiopp_bp.route("/api/multiopps/<int:multiopp_id>/mappings", methods=["GET"])
@require_auth
def get_multiopp_mappings_compact(multiopp_id):
    """
    Return compact mappings for a MultiOpportunity in the format:
    { "mappings": [ { "from": { "Tuesday": ["22:16", 60] }, "to": {} }, ... ] }
    """
    from collections import OrderedDict
    import pytz

    multiopp = MultiOpportunity.query.get_or_404(multiopp_id)
    opportunities = Opportunity.query.filter_by(multiopp_id=multiopp_id).all()

    eastern = pytz.timezone("US/Eastern")
    weekdays = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

    # Build a deterministic ordered set of unique (weekday, time, duration) tuples
    uniq = OrderedDict()
    for opp in opportunities:
        if not opp.date:
            continue
        local = opp.date.astimezone(eastern)
        day = weekdays[local.weekday()]
        time_str = local.strftime("%H:%M")
        duration = opp.duration or 60
        key = (day, time_str, int(duration))
        if key not in uniq:
            uniq[key] = {"day": day, "time": time_str, "duration": int(duration), "count": 1, "opp_ids":[opp.id]}
        else:
            uniq[key]["count"] += 1
            uniq[key]["opp_ids"].append(opp.id)

    # Convert to requested compact mappings array (to is empty by default)
    mappings = []
    for v in uniq.values():
        mappings.append({
            "from": { v["day"]: [ v["time"], v["duration"] ] },
            "to": {}
        })

    return jsonify({
        "multiopp_id": multiopp_id,
        "name": multiopp.name,
        "total_slots": len(opportunities),
        "mappings": mappings
    }), 200

@multiopp_bp.route("/api/multiopps/<int:multiopp_id>/remap_slots", methods=["PUT"])
@require_auth
def remap_opportunity_slots_compact(multiopp_id):
    """
    Accept compact mappings in the format:
    {
      "mappings": [
        { "from": { "Tuesday": ["22:16", 60] }, "to": { "Tuesday": ["23:16", 60] } },
        ...
      ]
    }

    For each mapping:
      - find all Opportunity rows for the multiopp that occur on `from_day` at `from_time`
      - update each opp's datetime to the `to_day` + `to_time` (same or shifted weekday)
      - update multiopp.days_of_week JSON replacing matched slot(s) with the new `to` slot
      - avoid creating duplicate opps at the same UTC instant (report conflict)
    """
    import pytz
    from datetime import datetime, time, timedelta

    payload = request.get_json(force=True, silent=True)
    if not payload or "mappings" not in payload:
        return jsonify({"error": "Request must include 'mappings' list."}), 400

    mappings = payload["mappings"]
    if not isinstance(mappings, list):
        return jsonify({"error": "'mappings' must be a list."}), 400

    multiopp = MultiOpportunity.query.get_or_404(multiopp_id)
    eastern = pytz.timezone("US/Eastern")
    weekdays = { "Monday":0,"Tuesday":1,"Wednesday":2,"Thursday":3,"Friday":4,"Saturday":5,"Sunday":6 }

    # Helper: parse compact slot [ "HH:MM", duration ] -> (timeobj, int)
    def parse_compact_slot(slot):
        if not isinstance(slot, (list, tuple)) or len(slot) < 2:
            raise ValueError("slot must be [timeStr, duration]")
        t = datetime.strptime(slot[0], "%H:%M").time()
        d = int(slot[1])
        return t, d

    # Load all current opportunities for this multiopp (will modify in place)
    opps = Opportunity.query.filter_by(multiopp_id=multiopp_id).order_by(Opportunity.date).all()
    if not opps:
        return jsonify({"error":"No opportunities found for this MultiOpportunity."}), 400

    # Build lookup from (weekday_index, "HH:MM", duration) -> [opp...]
    lookup = {}
    for opp in opps:
        if not opp.date:
            continue
        local = opp.date.astimezone(eastern)
        key = (local.weekday(), local.strftime("%H:%M"), int(opp.duration or 60))
        lookup.setdefault(key, []).append(opp)

    updated = []
    conflicts = []
    skipped = []
    multiopp_days = multiopp.days_of_week or []

    # Helper: find & replace in multiopp.days_of_week JSON
    # multiopp.days_of_week is expected like: [ { "Monday":[["21:21",60], ...] }, ... ]
    def replace_in_multiopp_days(from_day, from_time_str, from_dur, to_day, to_time_str, to_dur):
        replaced = 0
        for entry in multiopp_days:
            # each entry is {dayname: [ [time,dur], ... ]}
            for dayname, slots in entry.items():
                if dayname != from_day:
                    continue
                # replace any slot that exactly matches time+duration, preserving order
                for i, s in enumerate(slots):
                    # s may be ["HH:MM", dur]
                    if len(s) >= 2 and s[0] == from_time_str and int(s[1]) == int(from_dur):
                        # remove this slot and insert target slot into the appropriate day entry later
                        slots.pop(i)
                        replaced += 1
                        break  # only one replacement at a time here (keeps order)
        # now insert to_slot into to_day entry (append to end of that day's slots)
        inserted = 0
        for entry in multiopp_days:
            for dayname, slots in entry.items():
                if dayname == to_day:
                    slots.append([to_time_str, int(to_dur)])
                    inserted += 1
                    break
        # if the to_day doesn't exist in multiopp_days, create a new entry
        if inserted == 0:
            multiopp_days.append({ to_day: [ [to_time_str, int(to_dur)] ] })
            inserted = 1
        return replaced, inserted

    # Validate all mappings first (quick sanity checks)
    for mapping in mappings:
        if not isinstance(mapping, dict) or "from" not in mapping or "to" not in mapping:
            return jsonify({"error":"Each mapping must be an object with 'from' and 'to' keys."}), 400
        # validate from has one key and to has one key
        if not mapping["from"] or not isinstance(mapping["from"], dict):
            return jsonify({"error":"'from' must be an object like { 'Tuesday': ['22:16',60] }"}), 400
        if not mapping["to"] or not isinstance(mapping["to"], dict):
            return jsonify({"error":"'to' must be an object like { 'Tuesday': ['23:16',60] }"}), 400

    # Apply mappings
    for mapping in mappings:
        # Expect exactly one key under from and one under to
        try:
            from_day, from_slot = next(iter(mapping["from"].items()))
            to_day, to_slot = next(iter(mapping["to"].items()))
        except StopIteration:
            skipped.append({"mapping": mapping, "reason": "empty from/to"})
            continue

        if from_day not in weekdays or to_day not in weekdays:
            skipped.append({"mapping": mapping, "reason": "invalid weekday"})
            continue

        try:
            from_time_obj, from_dur = parse_compact_slot(from_slot)
            to_time_obj, to_dur = parse_compact_slot(to_slot)
        except Exception as e:
            skipped.append({"mapping": mapping, "reason": f"invalid slot format: {str(e)}"})
            continue

        from_key = (weekdays[from_day], from_time_obj.strftime("%H:%M"), int(from_dur))
        matching_opps = lookup.get(from_key, [])

        if not matching_opps:
            skipped.append({"mapping": mapping, "reason": "no matching opportunities"})
            continue

        # For each matching opp, compute new date/time and check for conflict
        for opp in matching_opps:
            old_local = opp.date.astimezone(eastern)
            # Compute candidate new local date:
            # If target weekday equals old weekday -> keep same date but change time
            # Otherwise shift forward (same week) to the next target weekday relative to old_local
            days_ahead = (weekdays[to_day] - old_local.weekday()) % 7
            new_local_date = (old_local + timedelta(days=days_ahead)).replace(
                hour=to_time_obj.hour, minute=to_time_obj.minute, second=0, microsecond=0
            )

            # Localize (already tz-aware) and convert to UTC for storage
            new_utc = new_local_date.astimezone(pytz.utc)

            # Conflict check: is there already another opportunity at new_utc?
            conflict = Opportunity.query.filter(
                Opportunity.multiopp_id == multiopp_id,
                Opportunity.date == new_utc
            ).first()
            if conflict and conflict.id != opp.id:
                conflicts.append({
                    "mapping": mapping,
                    "opp_id": opp.id,
                    "conflict_with": conflict.id,
                    "new_date": new_utc.isoformat()
                })
                continue

            # Apply updates to the opp
            opp.date = new_utc
            opp.duration = int(to_dur)
            updated.append(opp)

        # Update the multiopp.days_of_week JSON: replace one matching slot with the target slot
        replaced, inserted = replace_in_multiopp_days(from_day, from_time_obj.strftime("%H:%M"), from_dur,
                                                     to_day, to_time_obj.strftime("%H:%M"), to_dur)
        # Note: replace_in_multiopp_days will remove the first matching slot and append the target
        # We won't strictly require replaced==1 because there may be multiple identical slots; this mirrors updating one recurrence slot.
        # If you want to enforce exact counts, add additional validation here.

    # Persist changes and updated multiopp.days_of_week
    try:
        multiopp.days_of_week = multiopp_days
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error":"Database error while committing changes","details": str(e)}), 500

    return jsonify({
        "message": "Remap applied (some mappings may have skipped/conflicted).",
        "updated_count": len(updated),
        "conflict_count": len(conflicts),
        "skipped_count": len(skipped),
        "details": {
            "updated_ids": [o.id for o in updated],
            "conflicts": conflicts,
            "skipped": skipped,
            "new_days_of_week": multiopp.days_of_week
        }
    }), 200

# @multiopp_bp.route("/api/multiopps/<int:multiopp_id>/add_recurrences", methods=["POST"])
# @require_auth
# def add_recurrences_to_multiopp(multiopp_id):
#     """
#     Add additional recurrences (weeks) to an existing MultiOpportunity.
#     Expects JSON: { "additional_weeks": int }
#     This will increase week_recurrences and generate new opportunities starting from the next week.
#     """
#     try:
#         multiopp = MultiOpportunity.query.get_or_404(multiopp_id)
        
#         data = request.get_json(force=True, silent=True)
#         if not data or "additional_weeks" not in data:
#             return jsonify({"error": "Request must include 'additional_weeks' (integer)."}), 400
        
#         additional_weeks = int(data["additional_weeks"])
#         if additional_weeks <= 0:
#             return jsonify({"error": "'additional_weeks' must be a positive integer."}), 400
        
#         # Find the maximum week_index already generated
#         existing_opps = Opportunity.query.filter_by(multiopp_id=multiopp_id).all()
#         if not existing_opps:
#             return jsonify({"error": "No existing opportunities found for this MultiOpportunity."}), 400
        
#         # Calculate the max week_index from existing opportunities
#         eastern = pytz.timezone("US/Eastern")
#         start_date = multiopp.start_date
#         max_week_index = 0
#         for opp in existing_opps:
#             if opp.date:
#                 local_date = opp.date.astimezone(eastern).date()
#                 weeks_diff = (local_date - start_date.date()).days // 7
#                 max_week_index = max(max_week_index, weeks_diff)
        
#         # New total weeks
#         new_total_weeks = max_week_index + 1 + additional_weeks
#         multiopp.week_recurrences = new_total_weeks
        
#         # Generate new opportunities starting from max_week_index + 1
#         new_opps = generate_additional_opportunities_from_multiopp(multiopp, data, start_week=max_week_index + 1, num_weeks=additional_weeks)
        
#         db.session.commit()
        
#         return jsonify({
#             "message": f"Added {additional_weeks} weeks of recurrences to MultiOpportunity {multiopp_id}.",
#             "multiopp": multiopp.serialize(),
#             "new_opportunities": [opp.serialize() for opp in new_opps]
#         }), 200
        
#     except Exception as e:
#         db.session.rollback()
#         print("Error in POST /api/multiopps/<id>/add_recurrences:")
#         traceback.print_exc()
#         return jsonify({
#             'message': 'Failed to add recurrences',
#             'error': str(e)
#         }), 500

# def generate_additional_opportunities_from_multiopp(multiopp: MultiOpportunity, data: dict, start_week: int, num_weeks: int):
#     """Generate additional opportunities from a MultiOpportunity starting from a specific week."""
#     from datetime import datetime, timedelta
#     import pytz

#     all_opps = []
#     start_date = multiopp.start_date

#     eastern = pytz.timezone("US/Eastern")

#     # Flatten day/time mapping list into (weekday, [(time_str, duration), ...]) pairs
#     day_time_pairs = []
#     for entry in multiopp.days_of_week:
#         for weekday, time_list in entry.items():
#             day_time_pairs.append((weekday, time_list))

#     week_frequency = multiopp.week_frequency or 1

#     for week_offset in range(num_weeks):
#         week_index = start_week + week_offset
#         # Handle every Nth week (e.g., every 2 weeks)
#         if week_frequency > 1 and week_index % week_frequency != 0:
#             continue

#         base_week_start = start_date + timedelta(weeks=week_index)

#         for weekday_name, time_list in day_time_pairs:
#             weekday_index = [
#                 "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
#             ].index(weekday_name)
#             day_date = base_week_start + timedelta(days=(weekday_index - base_week_start.weekday()) % 7)

#             for time_entry in time_list:
#                 # Each entry is a tuple or list: (start_time_str, duration)
#                 if isinstance(time_entry, (list, tuple)) and len(time_entry) == 2:
#                     start_time_str, duration = time_entry
#                 else:
#                     start_time_str, duration = time_entry, 60

#                 # Parse "HH:MM" or ISO "T" time
#                 start_time = (
#                     datetime.fromisoformat(start_time_str).time()
#                     if "T" in start_time_str
#                     else datetime.strptime(start_time_str, "%H:%M").time()
#                 )

#                 # Combine with date (naive datetime)
#                 naive_dt = datetime.combine(day_date.date(), start_time)

#                 # ✅ Localize to Eastern time, then convert to UTC for DB storage
#                 localized_dt = eastern.localize(naive_dt)
#                 dt_utc = localized_dt.astimezone(pytz.utc)
#                 allow_carpool = data.get('allow_carpool', 'false').lower() == "true"

#                 opp = Opportunity(
#                     name=data.get("name", multiopp.name),
#                     description=data.get("description", multiopp.description),
#                     causes=data.get("causes", multiopp.causes),
#                     tags=data.get("tags", multiopp.tags),
#                     address=data.get("address", multiopp.address),
#                     nonprofit=data.get("nonprofit", multiopp.nonprofit),
#                     image=data.get("image", multiopp.image),
#                     approved=data.get("approved", multiopp.approved),
#                     host_org_name=data.get("host_org_name", multiopp.host_org_name),
#                     qualifications=data.get("qualifications", multiopp.qualifications),
#                     visibility=data.get("visibility", multiopp.visibility),
#                     host_org_id=data.get("host_org_id", multiopp.host_org_id),
#                     host_user_id=data.get("host_user_id", multiopp.host_user_id),
#                     redirect_url=data.get("redirect_url", multiopp.redirect_url),
#                     total_slots=data.get("total_slots", multiopp.total_slots),
#                     allow_carpool=allow_carpool,

#                     # Recurrence-specific fields
#                     date=dt_utc,  # store in UTC
#                     duration=duration,
#                     recurring="recurring",
#                     comments=[],
#                     attendance_marked=False,
#                     actual_runtime=None,

#                     # Relationship
#                     multiopp_id=multiopp.id,
#                     multi_opportunity=multiopp,
#                 )

#                 db.session.add(opp)
#                 all_opps.append(opp)
#                 db.session.flush() 

#                 if allow_carpool:
#                     add_carpool(opp, 'multiopp')

#     db.session.commit()
#     return all_opps
