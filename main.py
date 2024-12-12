import os
import io
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.responses import Response
from pymongo import MongoClient
import gridfs
from bson import ObjectId
from typing import List
from pydantic import BaseModel
from uuid import uuid4
from decouple import config

# Initialize FastAPI
app = FastAPI()
DB_USERNAME = config("DB_USERNAME")
DB_PASSWORD = config("DB_PASSWORD")
# MongoDB Atlas Setup
MONGO_URI = f"mongodb+srv://{DB_USERNAME}:{DB_PASSWORD}@cluster0.sxt0w.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  # Replace with your MongoDB Atlas connection string
client = MongoClient(MONGO_URI)
db = client["image_storage"]
fs = gridfs.GridFS(db)

# Cloud Domain (Replace this with your actual cloud domain)
CLOUD_DOMAIN = "http://localhost:8000"  # Replace with your actual domain

# Utility function to generate public URLs for images stored in GridFS
def get_image_url(file_id: ObjectId):
    return f"{CLOUD_DOMAIN}/api/images/{file_id}"

# Pydantic Model for Response
class ImageURLs(BaseModel):
    id: str
    image_urls: List[str]

# CRUD Operations

# Upload Images
@app.post("/api/images", status_code=status.HTTP_201_CREATED, response_model=ImageURLs)
async def upload_images(files: List[UploadFile] = File(...)):
    # Generate a unique ID for this upload session
    unique_id = str(uuid4())
    uploaded_urls = []
    
    for file in files:
        # Read file content and store it in GridFS
        file_content = await file.read()
        
        # Store the file in GridFS
        grid_file = fs.put(file_content, filename=file.filename, metadata={"user_id": unique_id})
        
        # Generate the URL for the stored image
        image_url = get_image_url(grid_file)
        uploaded_urls.append(image_url)
    
    return {"id": unique_id, "image_urls": uploaded_urls}

# Get Images by ID
@app.get("/api/imagesurl/{id}", response_model=ImageURLs)
def get_images_by_id(id: str):
    # Retrieve images for the given ID from GridFS
    image_files = fs.find({"metadata.user_id": id})
    if not image_files.alive:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No images found for this ID")
    
    # Generate the URLs for the stored images
    image_urls = [get_image_url(file._id) for file in image_files]
    
    return {"id": id, "image_urls": image_urls}

# Serve Images from GridFS
@app.get("/api/images/{file_id}")
async def serve_image(file_id: str):
    # Retrieve the file from GridFS using the provided file ID
    try:
        grid_file = fs.get(ObjectId(file_id))
    except gridfs.errors.NoFile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    
    # Return the image as a response with correct content type
    return Response(content=grid_file.read(), media_type= grid_file.content_type)  # Adjust content type as per image type

# Delete All Images for an ID
@app.delete("/api/images/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_images_by_id(id: str):
    # Find all images related to the ID
    image_files = fs.find({"metadata.user_id": id})
    if not image_files.alive:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No images found for this ID")
    
    # Delete the files from GridFS
    for file in image_files:
        fs.delete(file._id)

    return {"detail": "All images deleted successfully."}

# Delete a Specific Image
@app.delete("/api/images/{id}/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_specific_image(id: str, file_id: str):
    # Find the specific image in GridFS
    try:
        grid_file = fs.get(ObjectId(file_id))
        if grid_file.metadata["user_id"] != id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image does not belong to this ID")
    except gridfs.errors.NoFile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    # Delete the specific image from GridFS
    fs.delete(ObjectId(file_id))

    return {"detail": "Image deleted successfully."}