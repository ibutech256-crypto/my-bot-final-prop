  
param($Path,$B64,$Append) 
$c=[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($B64)) 
if($Append){Add-Content -Path $Path -Value $c -Force}else{Set-Content -Path $Path -Value $c -Force} 
Write-Output OK:$Path 
