# This temp file can be deleted

# Find the second occurrence of 'if __name__' after line 900
cut = None
count = 0
for i, l in enumerate(lines):
    if i > 900 and 'if __name__' in l:
        count += 1
        if count == 1:
            cut = i
            break

if cut:
    with open('D:/CKD/Frontend/streamlit_app.py', 'w', encoding='utf-8') as f:
        f.writelines(lines[:cut])
    print(f"Truncated at line {cut}. File now has {cut} lines.")
else:
    print("No cut point found.")
