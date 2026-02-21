# This temp file can be deleted
cut=931
for i,l in enumerate(lines):
    if i>920 and i<960 and lines[i].strip().startswith('if __name__'):
        found=True
        # Get the SECOND one
        for j in range(i+1, min(i+20, len(lines))):
            if lines[j].strip().startswith('if __name__'):
                cut=j
                break
        break
open('streamlit_app.py','w',encoding='utf-8').writelines(lines[:cut])
print('done',cut)
