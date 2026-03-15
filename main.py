import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime
import re 

app = Flask(__name__)
CORS(app)

# --- 1. MongoDB Connection ---
uri = "mongodb+srv://wadikarshreeya_db_user:3ARMAvAQ8bFGJe7H@cluster0.jeuigc1.mongodb.net/?appName=Cluster0"
client = MongoClient(uri)
db = client['VaniBankDB']

# Collections
user_col = db['user'] 
accounts_col = db['bank_accounts']
trans_col = db['transactions']

@app.route('/process_voice', methods=['POST'])
def process_voice():
    try:
        data = request.json
        uid = str(data.get('uid')).strip() 
        command = data.get('command', '').lower()
        lang = data.get('lang', 'mr') 
        user_pin = data.get('pin')

        # १. युजर आणि बँक माहिती मिळवणे
        sender = user_col.find_one({"user_id": uid})
        sender_acc = accounts_col.find_one({"user_id": uid})

        if not sender or not sender_acc:
            return jsonify({"status": "error", "message": "तुमचे खाते सापडले नाही."})

        # --- २. व्हॉइस कमांड लॉजिक ---

        # A. बॅलन्स तपासणे (Dashboard.js च्या लॉजिकशी सुसंगत)
        if any(word in command for word in ["balance", "पैसे", "शिल्लक", "बॅलन्स"]):
            return jsonify({
                "status": "success",
                "intent": "CHECK_BALANCE",
                "lang": lang,
                "payload": {
                    "name": sender.get('name', 'User'),
                    "bank": sender_acc.get('bank_name', 'Vani Bank'),
                    "balance": sender_acc.get('balance', 0)
                }
            })

        # B. पैसे पाठवणे
        elif any(word in command for word in ["send", "transfer", "pathav", "पाठव", "दे"]):
            amount_match = re.findall(r'\d+', command)
            amount = int(amount_match[0]) if amount_match else 0
            
            if amount <= 0:
                return jsonify({"status": "error", "message": "कृपया किती पैसे पाठवायचे आहेत ते सांगा."})

            all_users = list(user_col.find({}, {"name": 1, "user_id": 1}))
            receiver_id = None
            receiver_name = ""

            for u in all_users:
                if u['name'].lower() in command:
                    receiver_id = u['user_id']
                    receiver_name = u['name']
                    break

            if not receiver_id:
                return jsonify({"status": "error", "message": "ज्याला पैसे पाठवायचे आहेत त्याचे नाव सापडले नाही."})

            # Security: Pin Check
            if not user_pin:
                return jsonify({
                    "status": "pending",
                    "intent": "SEND_MONEY",
                    "message": f"तुम्ही {receiver_name} ला {amount} रुपये पाठवत आहात. व्यवहार पूर्ण करण्यासाठी तुमचा पिन सांगा.",
                    "action": "ASK_PIN",
                    "pending_data": {"amount": amount, "receiver_id": receiver_id}
                })

            correct_pin = sender_acc.get('pin', '1234')
            if str(user_pin) != str(correct_pin):
                return jsonify({"status": "error", "message": "चुकीचा पिन! व्यवहार रद्द झाला."})

            if sender_acc['balance'] >= amount:
                accounts_col.update_one({"user_id": uid}, {"$inc": {"balance": -amount}})
                accounts_col.update_one({"user_id": receiver_id}, {"$inc": {"balance": amount}})
                
                trans_col.insert_one({
                    "sender": uid,
                    "receiver": receiver_id,
                    "amount": amount,
                    "status": "Success",
                    "date": datetime.now()
                })
                
                return jsonify({
                    "status": "success", 
                    "message": f"यशस्वी! {receiver_name} ला {amount} रुपये पाठवले आहेत."
                })
            else:
                return jsonify({"status": "error", "message": "पुरेसा बॅलन्स नाही."})

        return jsonify({"status": "error", "message": "मला तुमची कमांड समजली नाही."})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)