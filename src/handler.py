import runpod
import base64
import tempfile
import os
from paddlex import create_pipeline
from typing import List, Dict, Any

# Initialize logger
log = runpod.RunPodLogger()

# Initialize pipeline at module level
log.info("Booting PaddleOCR-VL pipeline...")
try:
    pipeline = create_pipeline("PaddleOCR-VL", config="/home/paddleocr/pipeline_config_fastdeploy.yaml")
    log.info("Pipeline ready.")
except Exception as e:
    log.error(f"Failed to initialize pipeline: {str(e)}")
    raise


def process_single_file(file_base64: str, file_type: str, file_id: str = None) -> Dict[str, Any]:
    """
    Process a single file through OCR pipeline

    Args:
        file_base64: Base64 encoded file content
        file_type: Type of file (image/pdf)
        file_id: Optional identifier for the file

    Returns:
        Dictionary with processing results
    """
    file_identifier = file_id or "unknown"
    log.info(f"[File {file_identifier}] Processing file of type: {file_type}")

    # Determine file suffix based on type
    file_type_lower = file_type.lower()
    if file_type_lower == "pdf":
        suffix = ".pdf"
    elif file_type_lower in ["image", "img", "png", "jpg", "jpeg"]:
        suffix = ".png"
    else:
        log.warn(f"[File {file_identifier}] Unknown file_type '{file_type}', defaulting to .png")
        suffix = ".png"

    # Decode base64 file
    try:
        file_bytes = base64.b64decode(file_base64)
        log.debug(f"[File {file_identifier}] Decoded {len(file_bytes)} bytes")
    except Exception as e:
        log.error(f"[File {file_identifier}] Failed to decode base64: {str(e)}")
        return {"status": "error", "file_id": file_identifier, "error": f"Invalid base64 encoding: {str(e)}"}

    # Create temporary file
    file_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(file_bytes)
            file_path = f.name

        log.debug(f"[File {file_identifier}] Created temporary file: {file_path}")

        # Run OCR prediction
        log.info(f"[File {file_identifier}] Starting OCR prediction...")
        results = list(pipeline.predict(file_path))
        log.info(f"[File {file_identifier}] OCR completed, found {len(results)} page(s)")

        # Process results
        pages = []
        for i, r in enumerate(results):
            page_num = i + 1
            log.debug(f"[File {file_identifier}] Processing page {page_num}")

            # Extract result in the most appropriate format
            if hasattr(r, "json"):
                result_data = r.json
            elif hasattr(r, "to_dict"):
                result_data = r.to_dict()
            else:
                result_data = r

            pages.append({"page_number": page_num, "result": result_data})

        log.info(f"[File {file_identifier}] Successfully processed {len(pages)} page(s)")

        return {"status": "success", "file_id": file_identifier, "num_pages": len(pages), "pages": pages}

    except Exception as e:
        log.error(f"[File {file_identifier}] Error processing file: {str(e)}", exc_info=True)
        return {"status": "error", "file_id": file_identifier, "error": str(e)}
    finally:
        # Clean up temporary file
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                log.debug(f"[File {file_identifier}] Temporary file removed: {file_path}")
            except Exception as e:
                log.warn(f"[File {file_identifier}] Failed to remove temporary file: {str(e)}")


def handler(event):
    """
    RunPod serverless handler for PaddleOCR-VL pipeline
    Supports both single file and batch processing

    Single file input format:
    {
        "input": {
            "file_base64": "<base64_encoded_file>",
            "file_type": "image" or "pdf"  # optional, defaults to "image"
        }
    }

    Batch input format:
    {
        "input": {
            "batch": true,
            "files": [
                {
                    "file_base64": "<base64_encoded_file>",
                    "file_type": "image",
                    "file_id": "optional_identifier"
                },
                {
                    "file_base64": "<base64_encoded_file>",
                    "file_type": "pdf",
                    "file_id": "optional_identifier"
                }
            ]
        }
    }
    """
    job_id = event.get("id", "unknown")
    log.info(f"[Job {job_id}] Received OCR request")

    try:
        # Extract input data
        input_data = event.get("input", {})

        if not input_data:
            log.error(f"[Job {job_id}] No input data provided")
            return {"status": "error", "error": "No input data provided"}

        # Check if this is a batch request
        is_batch = input_data.get("batch", False)

        if is_batch:
            # Batch processing mode
            files = input_data.get("files", [])

            if not files:
                log.error(f"[Job {job_id}] Batch mode enabled but no files provided")
                return {"status": "error", "error": "No files provided in batch"}

            if not isinstance(files, list):
                log.error(f"[Job {job_id}] 'files' must be a list")
                return {"status": "error", "error": "'files' must be a list"}

            log.info(f"[Job {job_id}] Batch processing mode: {len(files)} file(s)")

            results = []
            successful = 0
            failed = 0

            for idx, file_data in enumerate(files):
                file_id = file_data.get("file_id", f"file_{idx + 1}")
                file_base64 = file_data.get("file_base64")
                file_type = file_data.get("file_type", "image")

                if not file_base64:
                    log.warn(f"[Job {job_id}] Skipping file {file_id}: no file_base64")
                    results.append({"status": "error", "file_id": file_id, "error": "file_base64 is required"})
                    failed += 1
                    continue

                # Process the file
                result = process_single_file(file_base64, file_type, file_id)
                results.append(result)

                if result["status"] == "success":
                    successful += 1
                else:
                    failed += 1

            log.info(f"[Job {job_id}] Batch completed: {successful} successful, {failed} failed")

            return {
                "status": "success",
                "batch": True,
                "total_files": len(files),
                "successful": successful,
                "failed": failed,
                "results": results,
            }

        else:
            # Single file processing mode
            file_base64 = input_data.get("file_base64")
            file_type = input_data.get("file_type", "image")

            # Validate required fields
            if not file_base64:
                log.error(f"[Job {job_id}] file_base64 missing in input")
                return {"status": "error", "error": "file_base64 is required"}

            log.info(f"[Job {job_id}] Single file processing mode")

            # Process the file
            result = process_single_file(file_base64, file_type)
            return result

    except Exception as e:
        log.error(f"[Job {job_id}] Error processing OCR request: {str(e)}", exc_info=True)
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    log.info("Starting RunPod serverless worker...")
    runpod.serverless.start({"handler": handler})
