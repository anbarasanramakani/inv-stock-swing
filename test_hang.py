import time
import concurrent.futures
import institutional as inst

def get_with_timeout():
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(inst.get_recent_bulk_deals)
        try:
            return future.result(timeout=10)
        except concurrent.futures.TimeoutError:
            print("Timeout!")
            return None
        except Exception as e:
            print(f"Exception: {e}")
            return None

print("Testing inst.get_recent_bulk_deals() with timeout...")
t1 = time.time()
res = get_with_timeout()
print(f"Result after {time.time() - t1:.2f}s: {type(res)}")
