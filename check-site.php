<?php
require("telegram.php");

$data = [];
$indx = (int)filter_input(INPUT_GET, "indx", FILTER_SANITIZE_NUMBER_INT);

$data["status"] = "";
$data["message"] = "";
$data["validate"] = "";
$data["validate_check"] = "";


$jsonData = file_get_contents('sites.json');
$sites = json_decode($jsonData, true);
$site = $sites[$indx] ?? null;
if (is_null($site)) {
    $data["status"] = "error";
    $data["message"] = "❌ ❌ ❌ chave inválida";
    echo json_encode($data);
    exit;
}

$url = $site['url'];
$title = $site['title'] ?? "";
$body = $site['body'] ?? "";



$headers = @get_headers($url);
$data["headers"] = $headers;
if ($headers && strpos($headers[0], '200')) {

    $html = file_get_contents($url);
    if ($html === false) {
        $data["status"] = "error";
        $data["message"] = "❌ erro ao acessar url";
    } else {
        $data["status"] = "success";
        $data["message"] = "✔️ validado";

        preg_match("/<title>(.*?)<\/title>/i", $html, $matches);
        if ($title <> "") {
            $data["validate_check"] = "❌";
            if (isset($matches[1])) {
                $data["validate"] = $matches[1];
                if (strpos(strtolower($data["validate"]), strtolower($title)) !== false) {
                    $data["validate_check"] = "✔️";
                } else {
                    $data["validate_check"] = "❌";
                }
            }
        } elseif ($body <> "") {
            if (strpos(strtolower($html), strtolower($body)) !== false) {
                $data["validate_check"] = "✔️";
            } else {
                $data["validate_check"] = "❌";
            }
        } else {
            $data["validate_check"] = "❗️";
        }
    }
} else {
    $data["status"] = "error";
    $data["message"] = "❌ site indisponível";
}

if ($data["status"] == "error") {
    foreach ($site["telegram"] ?? [] as $telegram) {
        sendTelegramMessage($telegram["bot_token"], $telegram["chat_id"], "Problemas detectados no site: " . $url . "<pre>" . $data["message"] . "</pre>");
    }
}

echo json_encode($data);
