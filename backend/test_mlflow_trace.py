import mlflow

mlflow.set_tracking_uri("http://localhost:5000")
mlflow.set_experiment("cadria-agents")

@mlflow.trace(name="CADRIA_TEST_TRACE", span_type="CHAIN")
def test_agent():
    return {
        "agent": "Scoping",
        "step": "Requirements analysis",
        "status": "success"
    }

print("Test result:", test_agent())

traces = mlflow.search_traces(locations=["1"])
print(traces)
