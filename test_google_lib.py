from googlesearch import search
import inspect

def test_google():
    print("Inspecting googlesearch.search parameters:")
    try:
        sig = inspect.signature(search)
        print(sig)
    except Exception as e:
        print(f"Error inspecting: {e}")

if __name__ == "__main__":
    test_google()
