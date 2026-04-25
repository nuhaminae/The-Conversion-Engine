# eval/harness.py
#
# This script uses Python's subprocess module to execute the tau2-bench command-line tool with the correct configuration.
# It loads your API keys, points the benchmark at your agent's URL, and saves the results in the right place.

import argparse
import os
import subprocess

from dotenv import load_dotenv


def run_evaluation(
    agent_url: str, output_path: str, num_trials: int, tasks: str, langfuse_host: str
):
    """
    Sets up the environment and runs the tau2-bench evaluation.

    Args:
        agent_url (str): The full URL of the running agent's API endpoint.
        output_path (str): The directory to save the evaluation results.
        num_trials (int): The number of trials to run for the benchmark.
        tasks (str): The task suite to run (e.g., 'dev' for the 30 dev tasks).
        langfuse_host (str): The host URL for the Langfuse server.
    """
    print("--- Starting Evaluation Harness ---")

    # 1. Load environment variables from the root .env file
    # This ensures that API keys for Langfuse, OpenRouter, etc., are available to the subprocess.
    dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)
        print("Loaded environment variables from .env file.")
    else:
        print(
            "Warning: .env file not found at project root. Relying on system environment variables."
        )

    # 2. Check if the tau2-bench directory exists
    tau_bench_path = os.path.join(os.path.dirname(__file__), "tau2-bench")
    if not os.path.isdir(tau_bench_path):
        print("\nError: The 'tau2-bench' directory was not found in 'eval/'.")
        print(
            "Please clone the repository into the 'eval/' directory before running the harness."
        )
        print("git clone <tau2-bench-repo-url> eval/tau2-bench")
        return

    # 3. Set environment variables specifically for the benchmark run
    # These are picked up by tau2-bench and your agent.
    env = os.environ.copy()
    env["AGENT_URL"] = agent_url  # URL for the agent to be benchmarked
    env["LANGFUSE_HOST"] = langfuse_host  # Langfuse server URL

    # Langfuse keys should already be in the environment from the .env file
    if not env.get("LANGFUSE_SECRET_KEY") or not env.get("LANGFUSE_PUBLIC_KEY"):
        print(
            "Warning: Langfuse secret or public key not found in environment. Tracing may fail."
        )

    # 4. Construct the tau2-bench command
    # This assumes tau2-bench has a main entry point and accepts arguments for URL, tasks, trials, and output.
    # The command structure is hypothetical but represents a standard benchmark tool.
    command = [
        "python",
        "-m",
        "tau2_bench.main",  # Adjust if the entry point is different
        "--url",
        agent_url,
        "--tasks",
        tasks,
        "--trials",
        str(num_trials),
        "--output",
        output_path,
        "--llm",
        "qwen/qwen3-next-80b-a3b-thinking",  # Specifying the model as a good practice
    ]

    print(f"\nRunning evaluation with the following configuration:")
    print(f"  - Agent URL: {agent_url}")
    print(f"  - Tasks: {tasks}")
    print(f"  - Trials: {num_trials}")
    print(f"  - Output Path: {output_path}")
    print(f"  - Langfuse Host: {langfuse_host}")
    print(f"\nExecuting command: {' '.join(command)}")

    # 5. Execute the benchmark
    try:
        # We run this from the 'tau2-bench' directory to ensure all its internal modules are found.
        process = subprocess.Popen(
            command,
            cwd=tau_bench_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        # Stream the output in real-time
        while True:
            output = process.stdout.readline()
            if output == "" and process.poll() is not None:
                break
            if output:
                print(output.strip())

        rc = process.poll()
        if rc == 0:
            print("\n--- Evaluation Completed Successfully ---")
            print(f"Results saved to '{output_path}'.")
        else:
            print(f"\n--- Evaluation Failed with exit code {rc} ---")

    except FileNotFoundError:
        print(
            "\nError: 'python' command not found. Ensure Python is installed and in your PATH."
        )
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the tau2-bench evaluation harness for the Conversion Engine."
    )

    parser.add_argument(
        "--agent-url",
        type=str,
        default="http://127.0.0.1:8000",
        help="The URL of the running FastAPI agent to be evaluated.",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default=os.path.dirname(__file__),  # Defaults to the 'eval' directory
        help="Directory to save score_log.json and trace_log.jsonl.",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=1,
        help="Number of trials to run per task. The project requirement is 1.",
    )
    parser.add_argument(
        "--tasks", type=str, default="dev", help="The task suite to run (e.g., 'dev')."
    )
    parser.add_argument(
        "--langfuse-host",
        type=str,
        default="https://cloud.langfuse.com",
        help="The URL of the Langfuse server.",
    )

    args = parser.parse_args()

    # Before running, ensure the agent server is running in a separate terminal.
    print(
        "Reminder: Make sure your FastAPI agent is running and accessible at the specified URL."
    )
    input(f"Press Enter to start the evaluation against {args.agent_url}...")

    run_evaluation(
        agent_url=args.agent_url,
        output_path=args.output_path,
        num_trials=args.trials,
        tasks=args.tasks,
        langfuse_host=args.langfuse_host,
    )
