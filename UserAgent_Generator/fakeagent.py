from fake_useragent import UserAgent

def generate_independent_pool(platform_type, count=100):
    # Initialize the engine locked strictly to that platform category
    ua = UserAgent(platforms=platform_type)
    unique_pool = set()
    
    # Keep pulling until the set hits your target count limit
    while len(unique_pool) < count:
        unique_pool.add(ua.random)
        
    return list(unique_pool)

if __name__ == "__main__":
    # Generate 100 desktop strings (will contain mixed Windows, Mac, Linux strings)
    desktop_list = generate_independent_pool('desktop', 100)
    
    # Generate 100 mobile strings (will contain mixed Android and iPhone strings)
    mobile_list = generate_independent_pool('mobile', 100)
    
    # Save Desktops
    with open("fake_desktop.json", "w", encoding="utf-8") as f:
        f.write("\n".join(desktop_list))
        
    # Save Mobiles
    with open("fake_mobile.json", "w", encoding="utf-8") as f:
        f.write("\n".join(mobile_list))
        
    print(f"Success! Saved {len(desktop_list)} Desktops and {len(mobile_list)} Mobiles separately.")