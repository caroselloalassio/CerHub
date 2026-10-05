<?php
/**
 * Plugin Name: CER Hub – Privacy e consenso cookie
 * Description: Banner di consenso senza servizi esterni, Google Analytics caricato solo dopo il consenso, protezione antispam del modulo di contatto senza servizi esterni, link a privacy e cookie policy nel piè di pagina.
 * Version: 1.1.1
 * Author: CER Hub
 * License: GPL-2.0-or-later
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

define( 'CERHUB_SITE_VERSION', '1.1.1' );

function cerhub_site_page_url( $slug ) {
	$page = get_page_by_path( $slug );
	return $page ? get_permalink( $page ) : home_url( '/' . $slug . '/' );
}

/**
 * 1. Consent Mode: tutto negato finché l'utente non sceglie. Va stampato prima di ogni altro script.
 */
function cerhub_site_consent_defaults() {
	try {
		$config = array(
			'policyUrl' => cerhub_site_page_url( 'cookie-policy' ),
			'gaId'      => null, // il tag di Google è già inserito da Site Kit: viene solo sbloccato dopo il consenso
		);
		echo "<script id=\"cerhub-consent-defaults\">window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}"
			. "gtag('consent','default',{ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied',analytics_storage:'denied'});"
			. 'window.CERHUB_CONSENT=' . wp_json_encode( $config ) . ";</script>\n";
	} catch ( \Throwable $e ) {
		return;
	}
}
add_action( 'wp_head', 'cerhub_site_consent_defaults', 0 );

/**
 * 2. Gli script statistici restano fermi (type="text/plain") finché non arriva il consenso.
 */
function cerhub_site_block_analytics( $tag, $handle, $src ) {
	try {
		if ( is_admin() || ! is_string( $tag ) || ! is_string( $src ) ) {
			return $tag;
		}
		$statistical = array( 'googletagmanager.com', 'google-analytics.com', 'stats.wp.com', 'pixel.wp.com' );
		$match       = false;
		foreach ( $statistical as $needle ) {
			if ( false !== strpos( $src, $needle ) ) {
				$match = true;
				break;
			}
		}
		if ( ! $match || false !== strpos( $tag, 'data-cerhub-consent' ) ) {
			return $tag;
		}
		// Il blocco vale per tutti gli script di questo gruppo: quello esterno e quelli "in linea" che lo accompagnano.
		$blocked = preg_replace( '/(<script\b[^>]*?)\stype=("|\')[^"\']*("|\')/i', '$1', $tag );
		$blocked = is_string( $blocked ) ? preg_replace( '/<script\b/i', '<script type="text/plain" data-cerhub-consent="analytics"', $blocked ) : null;
		return is_string( $blocked ) ? $blocked : $tag;
	} catch ( \Throwable $e ) {
		return $tag;
	}
}
add_filter( 'script_loader_tag', 'cerhub_site_block_analytics', 999, 3 );

/**
 * 3. Antispam del modulo di contatto senza servizi esterni (al posto di Google reCAPTCHA):
 *    un campo-trappola invisibile che le persone lasciano vuoto e un controllo sul tempo
 *    di compilazione. Nessun cookie, nessun dato inviato a terzi.
 */
function cerhub_site_antispam_fields( $html ) {
	try {
		if ( ! is_string( $html ) || false !== strpos( $html, 'cerhub_sito' ) ) {
			return $html;
		}
		return $html
			. '<p style="position:absolute;left:-10000px;top:auto;width:1px;height:1px;overflow:hidden;" aria-hidden="true">'
			. '<label>Lascia vuoto questo campo <input type="text" name="cerhub_sito" value="" tabindex="-1" autocomplete="off"></label></p>'
			. '<input type="hidden" name="cerhub_ts" value="">'
			. '<script>(function(){var s=document.currentScript,f=s&&s.parentNode;while(f&&f.tagName!=="FORM"){f=f.parentNode;}'
			. 'if(!f||!f.elements.cerhub_ts){return;}function t(){f.elements.cerhub_ts.value=String(Date.now());}t();'
			. 'f.addEventListener("reset",function(){setTimeout(t,0);});})();</script>';
	} catch ( \Throwable $e ) {
		return $html;
	}
}
add_filter( 'wpcf7_form_elements', 'cerhub_site_antispam_fields', 20 );

function cerhub_site_antispam_check( $spam ) {
	try {
		if ( $spam ) {
			return $spam;
		}
		// phpcs:disable WordPress.Security.NonceVerification.Missing
		$trap = isset( $_POST['cerhub_sito'] ) ? trim( (string) wp_unslash( $_POST['cerhub_sito'] ) ) : '';
		$ts   = isset( $_POST['cerhub_ts'] ) ? (float) wp_unslash( $_POST['cerhub_ts'] ) : 0;
		// phpcs:enable
		if ( '' !== $trap ) {
			return true;
		}
		$elapsed = microtime( true ) - ( $ts / 1000 );
		// compilato in meno di 4 secondi, oppure senza il valore impostato dal browser: è un programma
		if ( $ts <= 0 || $elapsed < 4 || $elapsed > DAY_IN_SECONDS ) {
			return true;
		}
		return false;
	} catch ( \Throwable $e ) {
		return $spam;
	}
}
add_filter( 'wpcf7_spam', 'cerhub_site_antispam_check', 20 );

/**
 * 4. Banner di consenso.
 */
function cerhub_site_enqueue_banner() {
	wp_enqueue_script( 'cerhub-consent', plugins_url( 'cerhub-consent.js', __FILE__ ), array(), CERHUB_SITE_VERSION, true );
}
add_action( 'wp_enqueue_scripts', 'cerhub_site_enqueue_banner', 20 );

/**
 * 5. Piè di pagina: privacy e cookie policy del sito al posto dei collegamenti esterni.
 */
function cerhub_site_footer_content( $value ) {
	try {
		if ( is_admin() ) {
			return $value;
		}
		$privacy = esc_url( cerhub_site_page_url( 'privacy-policy' ) );
		$cookie  = esc_url( cerhub_site_page_url( 'cookie-policy' ) );
		return '<p><a href="' . $privacy . '">Privacy Policy</a> &nbsp;&middot;&nbsp; <a href="' . $cookie . '">Cookie Policy</a>'
			. ' &nbsp;&middot;&nbsp; <a href="#" class="js-cerhub-cookie-prefs">Preferenze cookie</a></p>'
			. '<p style="letter-spacing: 2px; text-transform: uppercase;"><b>CER Hub</b><br>Codice Fiscale: 90076120097<br>'
			. '<a href="https://it.freepik.com" target="_blank" rel="noopener">Immagini di freepik</a></p>';
	} catch ( \Throwable $e ) {
		return $value;
	}
}
add_filter( 'option_x_footer_content', 'cerhub_site_footer_content', 20 );
add_filter( 'theme_mod_x_footer_content', 'cerhub_site_footer_content', 20 );

/**
 * 6. All'attivazione: indica a WordPress qual è la pagina della privacy.
 */
function cerhub_site_activate() {
	$page = get_page_by_path( 'privacy-policy' );
	if ( $page ) {
		update_option( 'wp_page_for_privacy_policy', (int) $page->ID );
	}
}
register_activation_hook( __FILE__, 'cerhub_site_activate' );
