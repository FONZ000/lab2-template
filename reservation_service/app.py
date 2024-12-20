from flask import Flask, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from os import environ
import uuid
from datetime import datetime
import requests
import logging


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = environ.get('DB_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class Hotel(db.Model):
    __tablename__ = 'hotel'

    id = db.Column(db.Integer, primary_key=True)
    hotel_uid = db.Column(db.String(36), unique=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    country = db.Column(db.String(80), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    stars = db.Column(db.Integer, nullable=True)  # Nullable for hotels without star ratings
    price = db.Column(db.Integer, nullable=False)  # Price per night

    # JSON representation
    def json(self):
        return {
            'id': self.id,
            'hotel_uid': self.hotel_uid,
            'name': self.name,
            'country': self.country,
            'city': self.city,
            'address': self.address,
            'stars': self.stars,
            'price': self.price
        }


class Reservation(db.Model):
    __tablename__ = 'reservation'

    id = db.Column(db.Integer, primary_key=True)
    reservation_uid = db.Column(db.String(36), unique=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), nullable=False)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotel.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="PAID")
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)

    __table_args__ = (
        db.CheckConstraint("status IN ('PAID', 'CANCELED')", name='valid_status_check'),
    )

    hotel = db.relationship('Hotel', backref=db.backref('reservations', lazy=True))

    def json(self):
        return {
            'id': self.id,
            'reservation_uid': self.reservation_uid,
            'username': self.username,
            'hotel_id': self.hotel.json() if self.hotel else None,
            'status': self.status,
            'start_date': self.start_date,
            'end_date': self.end_date
        }



with app.app_context():
    db.create_all()

#create a test route
@app.route('/test', methods = ['GET'])
def test():
    return make_response(jsonify({'message': 'test route'}), 200)

logging.basicConfig(level=logging.ERROR)

#create hotel
@app.route('/hotel', methods=['POST'])
def create_hotel():
    try:
        data = request.get_json()
        if not data or not all(key in data for key in ['name', 'country', 'city', 'address', 'stars', 'price']):
            return make_response(jsonify({'message': 'Invalid input data!'}), 400)

        new_hotel = Hotel(
            name=data['name'],
            country=data['country'],
            city=data['city'],
            address=data['address'],
            stars=data.get('stars'),  # Stars can be optional
            price=data['price']
        )
        db.session.add(new_hotel)
        db.session.commit()

        return make_response(jsonify({'message': 'Hotel created successfully!'}), 201)
    except Exception as e:
        logging.error(f"Error creating hotel: {e}")
        return make_response(jsonify({'message': 'Internal server error occurred.'}), 500)


#get all hotels
@app.route('/hotel', methods=['GET'])
def get_hotels():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        hotels = Hotel.query.paginate(page=page, per_page=per_page, error_out=False)
        return make_response(jsonify({'hotels': [hotel.json() for hotel in hotels.items]}), 200)
    except Exception as e:
        return make_response(jsonify({'message': 'Error getting hotels!'}), 500)


#get hotel by UID
@app.route('/hotel/<hotel_uid>', methods=['GET'])
def get_hotel(hotel_uid):
    try:
        hotel = Hotel.query.filter_by(hotel_uid=hotel_uid).first()
        if not hotel:
            return make_response(jsonify({'message': 'Hotel not found!'}), 404)
        return make_response(jsonify(hotel.json()), 200)
    except Exception as e:
        return make_response(jsonify({'message': f'Error fetching hotel: {str(e)}'}), 500)



#delete hotel
@app.route('/hotel/<hotel_uid>', methods = ['DELETE'])
def delete_hotel(hotel_uid):
    try:
        hotel = Hotel.query.filter_by(hotel_uid = hotel_uid).first()

        if hotel:
            db.session.delete(hotel)
            db.session.commit()
            return make_response(jsonify({'message': 'Hotel deleted successfully!'}), 200)
        return make_response(jsonify({'message': 'Hotel not found!'}))
    
    except Exception as e:
        return make_response(jsonify({'message': 'Error deleting hotel!'}), 500)



LOYALTY_SERVICE_URL = environ.get('LOYALTY_SERVICE_URL', "http://loyalty_service:8050/loyalty")

#create a reservation
@app.route('/reservation', methods=['POST'])
def create_reservation():
    try:
        data = request.get_json()
        username = request.headers.get('X-User-Name')

        if not username:
            return make_response(jsonify({'message': 'X-User-Name header is required'}), 400)

        loyalty_service_url = "http://loyalty_service:8050/loyalty"
        response = requests.get(f"{LOYALTY_SERVICE_URL}/{username}")

        if response.status_code == 404:
            return make_response(jsonify({'message': 'User not found in loyalty service!'}), 404)

        loyalty_user = response.json()

        # Validate input data
        required_fields = ['hotel_id', 'start_date', 'end_date']
        if not data or not all(field in data for field in required_fields):
            return make_response(jsonify({'message': 'Invalid input data!'}), 400)

        hotel = Hotel.query.filter_by(id=data['hotel_id']).first()
        if not hotel:
            return make_response(jsonify({'message': 'Hotel not found!'}), 404)

        start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')
        if start_date >= end_date:
            return make_response(jsonify({'message': 'Invalid date range!'}), 400)

        # Create reservation
        new_reservation = Reservation(
            hotel_id=data['hotel_id'],
            username=username,
            start_date=start_date,
            end_date=end_date
        )
        db.session.add(new_reservation)
        db.session.commit()

        # Notify loyalty service
        update_payload = {"reservation_count": loyalty_user["reservation_count"] + 1}
        patch_response = requests.patch(f"{loyalty_service_url}/{username}/", json=update_payload)

        if patch_response.status_code != 200:
            return make_response(jsonify({'message': 'Error updating loyalty data'}), patch_response.status_code)

        return make_response(jsonify(new_reservation.json()), 201)

    except Exception as e:
        logging.error(f"Error creating reservation: {e}")
        return make_response(jsonify({'message': 'Internal server error occurred.'}), 500)


#get all reservations
@app.route('/reservation', methods=['GET'])
def get_user_reservations():
    try:
        username = request.headers.get('X-User-Name')
        
        if not username:
            return make_response(jsonify({'message': 'X-User-Name header is required'}), 400)

        reservations = Reservation.query.filter_by(username=username).all()
        return make_response(jsonify({'reservations': [r.json() for r in reservations]}), 200)

    except Exception as e:
        return make_response(jsonify({'message': f'Error retrieving reservations: {str(e)}'}), 500)

#delete reservation
@app.route('/reservations/<reservation_uid>', methods=['DELETE'])
def cancel_reservation(reservation_uid):
    try:
        reservation = Reservation.query.filter_by(reservation_uid=reservation_uid).first()
        if not reservation:
            return make_response(jsonify({'message': 'Reservation not found!'}), 404)

        reservation.status = 'CANCELED'
        db.session.commit()

        # Notify the loyalty service to decrement the reservation count
        username = reservation.username
        loyalty_service_url = "http://loyalty_service:8050/loyalty"
        response = requests.get(f"{loyalty_service_url}/{username}")

        if response.status_code != 200:
            return make_response(jsonify({'message': 'Error fetching loyalty user'}), response.status_code)

        loyalty_user = response.json()
        new_count = max(0, loyalty_user["reservation_count"] - 1)  # Ensure count doesn't go below 0

        # Send PATCH request to update the reservation count
        patch_response = requests.patch(f"{loyalty_service_url}/{username}/", json={"reservation_count": new_count})

        if patch_response.status_code != 200:
            return make_response(jsonify({'message': 'Error updating loyalty user'}), patch_response.status_code)

        return make_response(jsonify({'message': 'Reservation canceled successfully!'}), 200)

    except Exception as e:
        return make_response(jsonify({'message': f'Error canceling reservation: {str(e)}'}), 500)


#get reservation by uid
@app.route('/reservations/<reservation_uid>', methods=['GET'])
def get_reservation(reservation_uid):
    reservation = Reservation.query.filter_by(reservation_uid=reservation_uid).first()
    if not reservation:
        return jsonify({'error': 'Reservation not found'}), 404
    return jsonify(reservation.json()), 200


#update reservation status
@app.route('/reservations/<reservation_uid>', methods=['PATCH'])
def update_reservation_status(reservation_uid):
    try:
        # Get the input data from the request body
        data = request.get_json()

        # Validate the input
        if not data or 'status' not in data:
            return make_response(jsonify({'message': 'Status field is required!'}), 400)

        new_status = data['status']

        # Validate the new status
        valid_statuses = ['PAID', 'CANCELED']
        if new_status not in valid_statuses:
            return make_response(jsonify({'message': f'Status must be one of {valid_statuses}'}), 400)

        # Find the reservation by its UID
        reservation = Reservation.query.filter_by(reservation_uid=reservation_uid).first()

        if not reservation:
            return make_response(jsonify({'message': 'Reservation not found!'}), 404)

        # Update the status
        reservation.status = new_status
        db.session.commit()

        return make_response(jsonify({'message': f'Reservation status updated to {new_status}!'}), 200)

    except Exception as e:
        return make_response(jsonify({'message': f'Error updating reservation status: {str(e)}'}), 500)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8070, debug=True)