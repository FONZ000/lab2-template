from flask import Flask, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from os import environ
import uuid
from datetime import datetime
import requests



app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = environ.get('DB_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

from flask_sqlalchemy import SQLAlchemy
import uuid

db = SQLAlchemy()

class Payment(db.Model):
    __tablename__ = 'payment'

    id = db.Column(db.Integer, primary_key=True)
    payment_uid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    reservation_id = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='PAID')
    price = db.Column(db.Integer, nullable=False)

    def json(self):
        return {
            'id': self.id,
            'payment_uid': self.payment_uid,
            'reservation_id': self.reservation_id,
            'status': self.status,
            'price': self.price
        }



with app.app_context():
    db.create_all()

#create a test route
@app.route('/test', methods = ['GET'])
def test():
    return make_response(jsonify({'message': 'test route'}), 200)


#create new payment
@app.route('/payment', methods=['POST'])
def create_payment():
    try:
        data = request.get_json()
        if not data or 'reservation_id' not in data or 'price' not in data:
            return make_response(jsonify({'message': 'Reservation ID and price are required!'}), 400)

        reservation_service_url = "http://reservation_service:8070/reservations"
        response = requests.get(f"{reservation_service_url}/{data['reservation_id']}")
        if response.status_code == 404:
            return make_response(jsonify({'message': 'Reservation not found!'}), 404)

        reservation = response.json()
        payment_status = 'PAID' if reservation['status'] == 'PAID' else 'PENDING'

        payment = Payment(
            reservation_id=data['reservation_id'],
            price=data['price'],
            status=payment_status
        )
        db.session.add(payment)
        db.session.commit()

        return make_response(jsonify({'message': 'Payment created successfully!', 'payment_uid': payment.payment_uid}), 201)
    except Exception as e:
        return make_response(jsonify({'message': f'Error creating payment: {str(e)}'}), 500)


    
#get payment by uid
@app.route('/payment/<payment_uid>', methods=['GET'])
def get_payment(payment_uid):
    try:
        payment = Payment.query.filter_by(payment_uid=payment_uid).first()
        if not payment:
            return make_response(jsonify({'message': 'Payment not found!'}), 404)
        
        return make_response(jsonify({
            'id': payment.id,
            'payment_uid': payment.payment_uid,
            'reservation_id': payment.reservation_id,
            'status': payment.status,
            'price': payment.price
        }), 200)
    except Exception as e:
        return make_response(jsonify({'message': f'Error fetching payment: {str(e)}'}), 500)
    

#update payment status
@app.route('/payment', methods=['POST'])
def create_payment():
    try:
        data = request.get_json()
        if not data or 'reservation_id' not in data or 'price' not in data:
            return make_response(jsonify({'message': 'Reservation ID and price are required!'}), 400)

        reservation_service_url = "http://reservation_service:8070/reservations"
        response = requests.get(f"{reservation_service_url}/{data['reservation_id']}")
        if response.status_code == 404:
            return make_response(jsonify({'message': 'Reservation not found!'}), 404)

        reservation = response.json()
        payment_status = 'PAID' if reservation['status'] == 'PAID' else 'PENDING'

        payment = Payment(
            reservation_id=data['reservation_id'],
            price=data['price'],
            status=payment_status
        )
        db.session.add(payment)
        db.session.commit()

        return make_response(jsonify({'message': 'Payment created successfully!', 'payment_uid': payment.payment_uid}), 201)
    except Exception as e:
        return make_response(jsonify({'message': f'Error creating payment: {str(e)}'}), 500)




#get all payments
@app.route('/payments', methods=['GET'])
def get_all_payments():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        payments = Payment.query.paginate(page=page, per_page=per_page, error_out=False)

        return make_response(jsonify({
            'payments': [
                {
                    'id': payment.id,
                    'payment_uid': payment.payment_uid,
                    'reservation_id': payment.reservation_id,
                    'status': payment.status,
                    'price': payment.price
                } for payment in payments.items
            ]
        }), 200)
    except Exception as e:
        return make_response(jsonify({'message': f'Error fetching payments: {str(e)}'}), 500)

#DELETE payment by uid
@app.route('/payment/<payment_uid>', methods=['DELETE'])
def delete_payment(payment_uid):
    try:
        payment = Payment.query.filter_by(payment_uid=payment_uid).first()
        if not payment:
            return make_response(jsonify({'message': 'Payment not found!'}), 404)

        username = request.headers.get('X-User-Name')
        if not username:
            return make_response(jsonify({'message': 'X-User-Name header is required'}), 400)

        # Notify loyalty service
        loyalty_service_url = "http://loyalty_service:8050/loyalty"
        if payment.status == 'PAID':
            requests.patch(f"{loyalty_service_url}/{username}/", json={"reservation_count": -1})

        db.session.delete(payment)
        db.session.commit()

        return make_response(jsonify({'message': 'Payment deleted successfully!'}), 200)
    except Exception as e:
        return make_response(jsonify({'message': f'Error deleting payment: {str(e)}'}), 500)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8060, debug=True)