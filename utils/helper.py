from services.s3_client import s3, S3_BUCKET
import pytz
from datetime import timedelta

# File upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Helper function to handle pagination
def paginate(query, page=1, per_page=20):
    return query.paginate(page=page, per_page=per_page, error_out=False)

# Helper functions for file uploads
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_opportunity_image(file, opportunity_id):
    """Save opportunity image to S3 with opportunity_id-based filename"""
    if file and allowed_file(file.filename):
        # Get file extension
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        
        # Create filename: image_{opportunity_id}.extension
        filename = f"image_{opportunity_id}.{file_extension}"
        
        # Upload to S3
        s3.upload_fileobj(
            file,
            S3_BUCKET,
            filename,
            ExtraArgs={"ContentType": file.content_type}
        )
        
        # Return the S3 URL
        return f"https://{S3_BUCKET}.s3.amazonaws.com/{filename}"
    
    return None

def format_datetime(dt_input, multiopp_id):
    """Format a datetime from the database (assume UTC) to US/Eastern local time."""
    dt_est = dt_input
    print(f"id: {multiopp_id}")
    if multiopp_id:
        print("yuper")
        dt_utc = pytz.utc.localize(dt_input)
        eastern = pytz.timezone('US/Eastern')
        dt_est = dt_utc.astimezone(eastern)
    else:
        dt_est = dt_input - timedelta(hours=4)

    short_format = dt_est.strftime('%-m/%-d/%y')  
    formal_format = dt_est.strftime('%B %-d, %Y, %-I:%M %p')  

    return {
        'short': short_format,
        'formal': formal_format,
        'datetime': dt_est.isoformat()
    }