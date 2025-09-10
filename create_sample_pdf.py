#!/usr/bin/env python3

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def create_sample_pdf():
    doc = SimpleDocTemplate("test_data/customer_data_format_spec.pdf", pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
    )
    
    story = []
    
    # Title
    story.append(Paragraph("Customer Data Format Specification", title_style))
    story.append(Paragraph("Version 1.0", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Overview
    story.append(Paragraph("1. Overview", heading_style))
    story.append(Paragraph(
        "This document describes the Customer Data Format v1.0, a standardized format for "
        "exchanging customer information between systems. The format supports customer profiles, "
        "order history, and product catalog data.",
        styles['Normal']
    ))
    story.append(Spacer(1, 12))
    
    # Customer Entity
    story.append(Paragraph("2. Customer Entity", heading_style))
    story.append(Paragraph("The customer entity contains the following fields:", styles['Normal']))
    story.append(Spacer(1, 6))
    
    customer_fields = [
        "<b>customer_id</b> (integer, required): Unique identifier for the customer",
        "<b>first_name</b> (string, required): Customer's first name, max 50 characters",
        "<b>last_name</b> (string, required): Customer's last name, max 50 characters", 
        "<b>email</b> (string, required): Customer's email address, must be valid email format",
        "<b>phone</b> (string, optional): Customer's phone number in format XXX-XXXX",
        "<b>registration_date</b> (date, required): Date customer registered, format YYYY-MM-DD",
        "<b>status</b> (enum, required): Customer status, values: 'active', 'inactive', 'suspended'"
    ]
    
    for field in customer_fields:
        story.append(Paragraph(f"• {field}", styles['Normal']))
    
    story.append(Spacer(1, 12))
    
    # Order Entity
    story.append(Paragraph("3. Order Entity", heading_style))
    story.append(Paragraph("The order entity represents customer purchases:", styles['Normal']))
    story.append(Spacer(1, 6))
    
    order_fields = [
        "<b>order_id</b> (string, required): Unique order identifier, format ORD-XXX",
        "<b>customer_id</b> (integer, required): Reference to customer entity",
        "<b>order_date</b> (date, required): Date order was placed, format YYYY-MM-DD",
        "<b>total_amount</b> (decimal, required): Total order amount with 2 decimal places",
        "<b>currency</b> (string, required): Currency code, ISO 4217 format (e.g., USD, EUR)",
        "<b>status</b> (enum, required): Order status, values: 'pending', 'completed', 'cancelled'",
        "<b>items</b> (array, required): Array of order items, each containing product details",
        "<b>shipping_address</b> (object, required): Shipping address information"
    ]
    
    for field in order_fields:
        story.append(Paragraph(f"• {field}", styles['Normal']))
    
    story.append(Spacer(1, 12))
    
    # Product Entity
    story.append(Paragraph("4. Product Entity", heading_style))
    story.append(Paragraph("The product entity describes items in the catalog:", styles['Normal']))
    story.append(Spacer(1, 6))
    
    product_fields = [
        "<b>product_id</b> (string, required): Unique product identifier, format PROD-XXX",
        "<b>name</b> (string, required): Product name, max 100 characters",
        "<b>category</b> (string, required): Product category",
        "<b>price</b> (decimal, required): Product price with currency attribute",
        "<b>description</b> (string, optional): Product description, max 500 characters",
        "<b>specifications</b> (object, optional): Technical specifications",
        "<b>availability</b> (object, required): Stock and availability information"
    ]
    
    for field in product_fields:
        story.append(Paragraph(f"• {field}", styles['Normal']))
    
    story.append(Spacer(1, 12))
    
    # Data Types and Constraints
    story.append(Paragraph("5. Data Types and Constraints", heading_style))
    story.append(Paragraph("The following data types and constraints apply:", styles['Normal']))
    story.append(Spacer(1, 6))
    
    constraints = [
        "<b>Dates</b>: Must be in ISO 8601 format (YYYY-MM-DD)",
        "<b>Email</b>: Must be valid email format with @ symbol",
        "<b>Phone</b>: Optional field, format XXX-XXXX when provided",
        "<b>Currency</b>: Must be valid ISO 4217 currency code",
        "<b>Enumerations</b>: Only specified values are allowed",
        "<b>Required fields</b>: Cannot be null or empty",
        "<b>String lengths</b>: Must not exceed specified maximum lengths"
    ]
    
    for constraint in constraints:
        story.append(Paragraph(f"• {constraint}", styles['Normal']))
    
    story.append(Spacer(1, 12))
    
    # Examples
    story.append(Paragraph("6. Usage Examples", heading_style))
    story.append(Paragraph(
        "Sample data files are provided showing the format in CSV, JSON, and XML formats. "
        "These demonstrate the relationships between entities and proper field formatting.",
        styles['Normal']
    ))
    
    doc.build(story)
    print("Sample PDF created: test_data/customer_data_format_spec.pdf")

if __name__ == "__main__":
    create_sample_pdf()