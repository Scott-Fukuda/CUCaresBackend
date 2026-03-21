from flask import Blueprint, request, jsonify
from utils.auth import require_auth
from db import db, FeedOrder, Opportunity, MultiOpportunity

feed_order_bp = Blueprint("feed_order", __name__)

def get_valid_ids():
    opp_ids = {r.id for r in Opportunity.query.filter_by(multiopp_id=None).with_entities(Opportunity.id).all()}
    multiopp_ids = {r.id for r in MultiOpportunity.query.with_entities(MultiOpportunity.id).all()}
    return opp_ids, multiopp_ids

def sync_order(stored, opp_ids, multiopp_ids):
    # remove deleted entries
    cleaned = [
        item for item in stored
        if (not item["is_multiopp"] and item["id"] in opp_ids)
        or (item["is_multiopp"] and item["id"] in multiopp_ids)
    ]
    # append new entries not yet in the stored order
    stored_opp_ids = {item["id"] for item in cleaned if not item["is_multiopp"]}
    stored_multiopp_ids = {item["id"] for item in cleaned if item["is_multiopp"]}
    new_entries = (
        [{"id": i, "is_multiopp": False} for i in opp_ids - stored_opp_ids] +
        [{"id": i, "is_multiopp": True} for i in multiopp_ids - stored_multiopp_ids]
    )
    return cleaned + new_entries

@feed_order_bp.route("/api/feed-order", methods=["GET"])
@require_auth
def get_feed_order():
    opp_ids, multiopp_ids = get_valid_ids()
    feed_order = FeedOrder.query.first()

    if not feed_order or feed_order.order == []:
        order = (
            [{"id": i, "is_multiopp": False} for i in opp_ids] +
            [{"id": i, "is_multiopp": True} for i in multiopp_ids]
        )
    else:
        order = sync_order(feed_order.order, opp_ids, multiopp_ids)
        if order != feed_order.order:
            feed_order.order = order
            db.session.commit()

    return jsonify({"order": order}), 200

@feed_order_bp.route("/api/feed-order", methods=["PUT"])
@require_auth
def update_feed_order():
    body = request.get_json()
    order = body.get("order")
    if order is None or not isinstance(order, list):
        return jsonify({"error": "order must be a list of objects"}), 400
    if any(not isinstance(item, dict) or "id" not in item or "is_multiopp" not in item for item in order):
        return jsonify({"error": "each item must have 'id' and 'is_multiopp'"}), 400

    feed_order = FeedOrder.query.first()
    if not feed_order:
        feed_order = FeedOrder(order=order)
        db.session.add(feed_order)
    else:
        feed_order.order = order

    db.session.commit()
    return jsonify(feed_order.serialize()), 200
