import json

def verify_jeju():
    with open('cctv_data.json', 'r') as f:
        data = json.load(f)
    
    jeju_count = 0
    yeongsan_count = 0
    total_count = len(data)
    
    jeju_sample = None
    yeongsan_sample = None
    
    for item in data:
        if item['id'].startswith('JEJU_'):
            jeju_count += 1
            if item['id'] == 'JEJU_C62':
                jeju_sample = item
        elif item['id'].startswith('E') and 'yeongsanriver' in item.get('url', ''):
            yeongsan_count += 1
            if item['id'] == 'E630055':
                yeongsan_sample = item
                
    print(f"Total CCTV: {total_count}")
    print(f"Jeju ITS (JEJU_...): {jeju_count}")
    print(f"Yeongsan River (E...): {yeongsan_count}")
    
    if jeju_sample:
        print(f"Sample JEJU_C62 URL: {jeju_sample['url']}")
    else:
        print("JEJU_C62 NOT FOUND!")
        
    if yeongsan_sample:
        print(f"Sample E630055 URL: {yeongsan_sample['url']}")
    else:
        print("E630055 NOT FOUND!")

if __name__ == "__main__":
    verify_jeju()
