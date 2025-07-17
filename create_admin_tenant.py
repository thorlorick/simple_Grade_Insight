#!/usr/bin/env python3
"""
Script to create an admin tenant for development and testing
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import get_db
from app.models import Tenant, Teacher, Tag

def create_admin_tenant():
    """Create admin tenant with some default data"""
    db = next(get_db())
    
    try:
        # Check if admin tenant already exists
        existing_tenant = db.query(Tenant).filter(Tenant.id == "admin").first()
        
        if existing_tenant:
            print("Admin tenant already exists!")
            print(f"  ID: {existing_tenant.id}")
            print(f"  Name: {existing_tenant.name}")
            print(f"  Created: {existing_tenant.created_at}")
            return existing_tenant
        
        # Create admin tenant
        admin_tenant = Tenant(
            id="admin",
            name="Admin Tenant - Development"
        )
        
        db.add(admin_tenant)
        db.commit()
        db.refresh(admin_tenant)
        
        print("✅ Successfully created admin tenant!")
        print(f"  ID: {admin_tenant.id}")
        print(f"  Name: {admin_tenant.name}")
        
        # Create default admin teacher
        admin_teacher = Teacher(
            name="Admin Teacher",
            email="admin@gradeinsight.com",
            tenant_id="admin"
        )
        
        db.add(admin_teacher)
        db.commit()
        db.refresh(admin_teacher)
        
        print("✅ Created default admin teacher!")
        print(f"  Name: {admin_teacher.name}")
        print(f"  Email: {admin_teacher.email}")
        
        # Create some default tags for admin
        default_tags = [
            "Homework",
            "Quiz",
            "Test",
            "Project",
            "Extra Credit",
            "Participation"
        ]
        
        created_tags = []
        for tag_name in default_tags:
            tag = Tag(
                name=tag_name,
                tenant_id="admin"
            )
            db.add(tag)
            created_tags.append(tag)
        
        db.commit()
        
        print("✅ Created default tags:")
        for tag in created_tags:
            print(f"  - {tag.name}")
        
        print("\n🎉 Admin tenant setup complete!")
        print("\nYou can now access:")
        print("  - Dashboard: http://localhost:8000/dashboard")
        print("  - Upload: http://localhost:8000/upload")
        print("  - API: http://localhost:8000/api/dashboard/stats")
        
        return admin_tenant
        
    except Exception as e:
        print(f"❌ Error creating admin tenant: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def update_tenant_function_for_admin():
    """Show the updated get_tenant_from_host function"""
    print("\n📝 Don't forget to update your get_tenant_from_host function in app/database.py:")
    print("""
def get_tenant_from_host(host: str) -> str:
    \"\"\"
    Extract tenant subdomain from host header safely.
    For development, defaults to 'admin' tenant.
    \"\"\"
    if not host:
        raise HTTPException(status_code=400, detail="Missing Host header")
    
    # Remove port if present
    host_without_port = host.split(":")[0]
    
    # Development mode: handle localhost, GitHub Codespaces, etc.
    if (host_without_port == "localhost" or 
        ".githubpreview.dev" in host_without_port or 
        ".github.dev" in host_without_port or
        ".gitpod.io" in host_without_port):
        return "admin"  # Default to admin tenant for development
    
    # Production mode: extract subdomain
    subdomain = host_without_port.split(".")[0].lower()
    
    if not subdomain or not re.fullmatch(r"[a-z0-9\-]+", subdomain):
        raise HTTPException(status_code=400, detail="Invalid tenant in host")
    
    return subdomain
""")

if __name__ == "__main__":
    print("🚀 Creating admin tenant...")
    create_admin_tenant()
    update_tenant_function_for_admin()
