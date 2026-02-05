<?php
require("telegram.php");

function apagarRecursivo($path)
{
    if (is_file($path) || is_link($path)) {
        unlink($path);
        return;
    }

    if (is_dir($path)) {
        foreach (scandir($path) as $item) {
            if ($item === '.' || $item === '..') {
                continue;
            }
            apagarRecursivo($path . DIRECTORY_SEPARATOR . $item);
        }
        rmdir($path);
    }
}



$data = [];
$send_telegram = false;

if (!isset($_GET["indx"])) {
    $indx = -1;
    $send_telegram = true;
} else {
    $indx = (int)filter_input(INPUT_GET, "indx", FILTER_SANITIZE_NUMBER_INT);
}


$jsonData = file_get_contents('sites.json');
$sites = json_decode($jsonData, true);
if ($indx >= 0) {
    $sites = [$sites[$indx]];
}

foreach ($sites as $key => $site) {
    $site = $sites[$key] ?? null;

    $data["status"] = "";
    $data["message"] = "";
    $data["validate"] = "";
    $data["validate_check"] = "";


    if (is_null($site)) {
        $data["status"] = "error";
        $data["message"] = "❌ ❌ ❌ chave inválida";
    } else {

        $url = $site['url'];
        $title = $site['title'] ?? "";
        $body = $site['body'] ?? "";



        $headers = @get_headers($url);
        $data["headers"] = $headers;
        if ($headers && strpos($headers[0], '200')) {

            $ch = curl_init($url);

            curl_setopt_array($ch, [
                CURLOPT_RETURNTRANSFER => true,   // retorna o HTML
                CURLOPT_FOLLOWLOCATION => true,   // segue redirect (HTTP → HTTPS)
                CURLOPT_TIMEOUT => 20,
                CURLOPT_CONNECTTIMEOUT => 10,
                CURLOPT_USERAGENT => 'Mozilla/5.0 (compatible; SiteFetcher/1.0)',
                CURLOPT_SSL_VERIFYPEER => true,
                CURLOPT_SSL_VERIFYHOST => 2,
            ]);

            $html = curl_exec($ch);

            if ($html === false) {
                $error = curl_error($ch);
                curl_close($ch);
                $data["status"] = "error";
                $data["message"] = "❌ erro ao acessar url: " . $error;
            } else {
                $data["status"] = "success";
                $data["message"] = "✔️ validado";

                preg_match("/<title>(.*?)<\/title>/is", $html, $matches);
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
            $data["message"] = "❌ site indisponível: " . $headers[0];
        }

        if ($data["validate_check"] == "❌") {
            $data["status"] = "error";
            $data["message"] = "❌ site com problemas";
        }

        if (isset($site["path"])) {
            if (isset($site["malicious_files"])) {
                $paths = [];
                if (is_array($site["path"])) {
                    $paths = $site["path"];
                } else {
                    $paths[] = $site["path"];
                }
                foreach ($paths as $path) {
                    $malicious_files_count = 0;
                    foreach ($site["malicious_files"] as $file) {
                        $f = $path . "/" . $file;
                        if (file_exists($f)) {
                            $malicious_files_count++;
                            apagarRecursivo($f);
                        }
                    }
                }

                if ($malicious_files_count > 0) {
                    $data["status"] = "error";
                    $data["message"] .= "<br>😈 arquivos maliciosos encontrados";
                }
            }
        }

        if ($data["status"] == "error") {
            if (isset($site["callback"])) {
                $url = $site["callback"];

                $ch = curl_init($url);
                curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
                curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
                curl_setopt($ch, CURLOPT_TIMEOUT, 10);

                $response = curl_exec($ch);
                if ($response === false) {
                    $data["message"] .= "<br>❌ Erro no callback: " . curl_error($ch);
                }
                curl_close($ch);
            }
        }

        if ($send_telegram && $data["status"] == "error") {
            foreach ($site["telegram"] ?? [] as $telegram) {
                sendTelegramMessage($telegram["bot_token"], $telegram["chat_id"], "Problemas detectados no site: " . $url . "<pre>" . $data["message"] . "</pre>");
            }
        }
    }
    echo json_encode($data);
}
