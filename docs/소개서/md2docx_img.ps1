param([string]$Html, [string]$Docx)
# HTML을 워드로 열어 docx로 저장하고 작성자 같은 문서 속성을 지운다. 그림은 뒤에 build_docx.py가 넣는다.
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $doc = $word.Documents.Open($Html, $false, $true)
    $doc.SaveAs2($Docx, 16)
    $doc.Close($false)
    $doc = $word.Documents.Open($Docx)
    $doc.RemoveDocumentInformation(99)
    $doc.Save()
    $doc.Close($false)
    "saved"
} finally { $word.Quit() }
