#(©)CodeXBotz

import pymongo, os
from config import DB_URI, DB_NAME

dbclient = pymongo.MongoClient(DB_URI)
database = dbclient[DB_NAME]
user_data = database['users']

async def present_user(user_id : int):
    found = user_data.find_one({'_id': user_id})
    return bool(found)

async def add_user(user_id: int):
    user_data.insert_one({'_id': user_id})
    return

async def full_userbase():
    user_docs = user_data.find()
    user_ids = []
    for doc in user_docs:
        user_ids.append(doc['_id'])
        
    return user_ids

async def del_user(user_id: int):
    user_data.delete_one({'_id': user_id})
    return


# Premium membership collections
premium_data = database['premium_memberships']
payment_requests = database['premium_payment_requests']

async def get_premium(user_id: int):
    from datetime import datetime, timezone
    doc = premium_data.find_one({'_id': user_id})
    if not doc:
        return None
    expires_at = doc.get('expires_at')
    if not expires_at:
        return None
    # MongoDB may return a naive datetime; treat it as UTC.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        premium_data.delete_one({'_id': user_id})
        return None
    return doc

async def create_payment_request(user_id: int, plan_days: int, amount: int):
    from datetime import datetime, timezone
    payment_requests.update_one(
        {'_id': user_id},
        {'$set': {'plan_days': plan_days, 'amount': amount, 'status': 'pending', 'created_at': datetime.now(timezone.utc)}},
        upsert=True
    )

async def get_payment_request(user_id: int):
    return payment_requests.find_one({'_id': user_id, 'status': 'pending'})

async def approve_premium(user_id: int, plan_days: int):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    current = await get_premium(user_id)
    start = current['expires_at'] if current and current.get('expires_at') and current['expires_at'] > now else now
    expires_at = start + timedelta(days=plan_days)
    premium_data.update_one({'_id': user_id}, {'$set': {'expires_at': expires_at}}, upsert=True)
    payment_requests.update_one({'_id': user_id}, {'$set': {'status': 'approved', 'approved_at': now, 'approved_days': plan_days}})
    return expires_at

async def reject_payment(user_id: int):
    payment_requests.update_one({'_id': user_id, 'status': 'pending'}, {'$set': {'status': 'rejected'}})
