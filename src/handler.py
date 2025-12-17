import runpod


def handler(job):
    """Handler function that will be used to process jobs."""
    job_input = job["input"]

    name = job_input.get("name", "World")

    return f"Hello, {name}!"


runpod.serverless.start({"handler": handler})
